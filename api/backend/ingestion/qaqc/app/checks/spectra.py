"""
QAQC checks for spectra.csv

Checks (in order):
  1. Mechanical — required columns, no missing values, castable types,
                  extra column warnings (integer band columns are excluded
                  from the extra-column check since they are dynamic).
                  Driven by checks/config/spectra.json.
  2. Band contiguity — integer-named band columns must be 0-based contiguous
                       (0, 1, 2, … N-1).
  3. Per row:
       a. Plot FK — (campaign_name, plot_name) must resolve.
       b. Plot-granule intersection FK — (campaign_name, plot_name, granule_id)
                                         must resolve to a known plot shape.
       c. Band count — number of band columns must match the wavelength count
                       declared for this campaign/sensor.
       d. Pixel uniqueness within file — (campaign, plot, granule, glt_row,
                                          glt_col) must not repeat.
       e. Pixel not in DB — same key must not already exist in production pixel.
       f. WGS84 bounds — lon must be -180..180, lat must be -90..90 (error).
       g. Pixel footprint intersects plot shape — a GSD × GSD square centred
                                                  on the pixel centroid must
                                                  intersect the plot polygon.
                                                  Falls back to centroid check
                                                  if GSD is unknown.
  4. Summarise coordinate and point-in-polygon errors into batch messages.
"""

from __future__ import annotations

import pandas as pd
from shapely.geometry import Point

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import (
    load_config, run_mechanical_checks,
    check_required_columns, check_no_missing_values,
    check_castable, check_extra_columns, check_foreign_key,
    _resolve_types,
)

CONFIG = load_config("spectra")
CONFIG["_file_name"] = "spectra"


def check(context: CheckContext) -> CheckResult:
    df = context.data["spectra"]

    band_cols = _identify_band_cols(df)

    errors, warnings = _run_mechanical_checks_excluding_band_cols(df, band_cols, context.enums)
    errors += _check_band_contiguity(band_cols)
    row_errors, row_warnings = _check_per_row(df, band_cols, context)
    errors   += row_errors
    warnings += row_warnings

    return CheckResult("spectra", len(df), errors, warnings)


# ── Band column helpers ────────────────────────────────────────────────────────

def _identify_band_cols(df: pd.DataFrame) -> list[int]:
    """
    Return sorted list of integer band column indices.
    Band columns are named with non-negative integers: "0", "1", "2", …
    """
    cols = []
    for col in df.columns:
        try:
            val = int(col)
            if val >= 0:
                cols.append(val)
        except (ValueError, TypeError):
            pass
    return sorted(cols)


def _run_mechanical_checks_excluding_band_cols(
    df: pd.DataFrame,
    band_cols: list[int],
    enums: dict,
) -> tuple[list[dict], list[dict]]:
    """
    Run the standard mechanical checks, but exclude integer-named band columns
    from the extra-column warning — they are dynamic and intentionally unnamed.
    """
    errors = check_required_columns(df, CONFIG.get("required_cols", []), "spectra")
    if errors:
        return errors, []

    errors   = (
        check_no_missing_values(df, CONFIG.get("required_cols", []), "spectra")
        + check_castable(df, _resolve_types(CONFIG.get("type_cols", {})), "spectra")
    )
    band_col_names = {str(b) for b in band_cols}
    non_band_df    = df[[c for c in df.columns if c not in band_col_names]]
    warnings = check_extra_columns(
        non_band_df,
        CONFIG.get("required_cols", []) + CONFIG.get("nullable_cols", []),
        "spectra",
    )
    return errors, warnings


# ── File-level checks ──────────────────────────────────────────────────────────

def _check_band_contiguity(band_cols: list[int]) -> list[dict]:
    """Band column headers must be 0-based contiguous integers (0, 1, 2 … N-1)."""
    if band_cols and band_cols != list(range(len(band_cols))):
        return [{
            "file": "spectra", "row": None, "column": None,
            "message": "band column headers are not 0-based contiguous integers",
        }]
    return []


# ── Per-row checks ─────────────────────────────────────────────────────────────

def _check_per_row(
    df: pd.DataFrame,
    band_cols: list[int],
    context: CheckContext,
) -> tuple[list[dict], list[dict]]:
    """
    Run all per-row checks in a single pass.
    Returns (errors, warnings).

    - Coordinate bounds violations and DB duplicate pixels are collected and
      summarised into batch messages to avoid flooding the report.
    - Point-in-polygon (footprint outside plot shape) is a warning, not an
      error — it includes distance bucketing so the severity can be assessed.
    """
    all_plots, all_shape_map, all_band_counts, all_gsd_map = _build_reference_sets(context)

    errors          = []
    warnings        = []
    pk_seen         = set()
    out_of_bounds   = []   # row numbers where lon/lat are outside WGS84 range
    outside_polygon = []   # (row_number, distance_m) — warning, not error

    for idx, row in df.iterrows():
        campaign = row["campaign_name"]
        plot     = row["plot_name"]
        sensor   = row["sensor_name"]
        granule  = row["granule_id"]
        plot_key = (campaign, plot)
        int_key  = (campaign, plot, granule)

        if plot_key not in all_plots:
            errors.append({
                "file": "spectra", "row": int(idx + 2), "column": "plot_name",
                "message": (
                    f"(campaign_name='{campaign}', plot_name='{plot}') "
                    f"not found in plots.geojson or database"
                ),
            })
            continue  # remaining checks depend on the plot resolving

        if int_key not in all_shape_map:
            errors.append({
                "file": "spectra", "row": int(idx + 2), "column": "granule_id",
                "message": (
                    f"(campaign_name='{campaign}', plot_name='{plot}', "
                    f"granule_id='{granule}') not found in plot_raster_intersect"
                ),
            })
            continue  # remaining checks depend on the intersection resolving

        errors += _check_band_count(campaign, sensor, band_cols, all_band_counts, idx)

        pk = (campaign, plot, granule, row["glt_row"], row["glt_column"])
        if pk in pk_seen:
            errors.append({
                "file": "spectra", "row": int(idx + 2), "column": None,
                "message": "duplicate pixel within file",
            })
        elif pk in context.db["pixel_set"]:
            errors.append({
                "file": "spectra", "row": int(idx + 2), "column": None,
                "message": "pixel already exists in database",
            })
        pk_seen.add(pk)

        row_out_of_bounds, row_outside_polygon = _check_coordinates(
            row, all_shape_map[int_key], all_gsd_map.get(granule), idx
        )
        out_of_bounds   += row_out_of_bounds
        outside_polygon += row_outside_polygon

    errors   += _summarise_coord_errors(
        out_of_bounds,
        "pixel(s) have lon/lat outside WGS84 bounds (-180..180, -90..90)",
    )
    warnings += _summarise_outside_polygon(outside_polygon)

    return errors, warnings


def _build_reference_sets(context: CheckContext) -> tuple[set, dict, dict, dict]:
    """Merge bundle and DB reference sets for plot FK, shape, band count, and GSD lookups."""
    all_plots = (
        set(context.output.get("plot_id_map", {}).keys())
        | context.db["plot_set"]
    )
    all_shape_map = {
        **context.db["plot_shape_map"],
        **context.output.get("plot_shape_map", {}),
    }
    all_band_counts = {
        **context.db["wavelength_band_counts"],
        **context.output.get("bundle_band_counts", {}),
    }
    all_gsd_map = {
        **context.db["granule_gsd_map"],
        **context.output.get("granule_gsd_map", {}),
    }
    return all_plots, all_shape_map, all_band_counts, all_gsd_map


def _check_band_count(
    campaign: str,
    sensor: str,
    band_cols: list[int],
    all_band_counts: dict,
    idx: int,
) -> list[dict]:
    """Number of band columns must match the wavelength count for this sensor."""
    expected = all_band_counts.get((campaign, sensor))
    if expected is not None and len(band_cols) != expected:
        return [{
            "file": "spectra", "row": int(idx + 2), "column": None,
            "message": (
                f"band column count ({len(band_cols)}) does not match "
                f"wavelength count ({expected}) for ({campaign}, {sensor})"
            ),
        }]
    return []


def _check_coordinates(
    row: pd.Series,
    plot_geom,
    gsd: float | None,
    idx: int,
) -> tuple[list[int], list[tuple[int, float]]]:
    """
    Check lon/lat for WGS84 bounds and pixel footprint intersection.
    Returns (out_of_bounds_rows, outside_polygon_entries).

    outside_polygon_entries is a list of (row_number, distance_m) where
    distance_m is the distance from the pixel centroid to the nearest point
    on the polygon boundary — used to bucket violations by severity.

    When GSD is known, constructs a GSD × GSD square centred on the pixel
    centroid (cap_style=3) and checks whether it intersects the plot polygon.
    This matches rioxarray's all_touched=True semantics — any pixel whose
    footprint overlaps the plot boundary is accepted.

    When GSD is unknown, falls back to a plain centroid intersects check.
    """
    try:
        lon = float(row["lon"])
        lat = float(row["lat"])
    except (ValueError, TypeError):
        return [], []  # non-castable values already caught by the type check

    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return [idx + 2], []  # skip footprint check if coordinates are garbage

    pt = Point(lon, lat)

    if gsd is not None:
        radius_deg      = (float(gsd) / 2) / 111320
        pixel_footprint = pt.buffer(radius_deg, cap_style=3)
        intersects      = plot_geom.intersects(pixel_footprint)
    else:
        intersects = plot_geom.intersects(pt)

    if not intersects:
        dist_m = plot_geom.exterior.distance(pt) * 111320
        return [], [(idx + 2, dist_m)]

    return [], []


def _summarise_outside_polygon(
    outside_polygon: list[tuple[int, float]],
) -> list[dict]:
    """
    Summarise pixel footprint violations bucketed by distance from the polygon
    boundary. Helps distinguish reprojection artefacts (< 1m) from genuine
    data errors (> 10m).

    Buckets:
      < 1m    — likely floating point / reprojection artefact
      1–10m   — possible polygon alignment issue, worth reviewing
      10–100m — outside normal tolerance, probable data error
      > 100m  — clearly misplaced pixel
    """
    if not outside_polygon:
        return []

    buckets = [
        (1,    "< 1m",     []),
        (10,   "1–10m",    []),
        (100,  "10–100m",  []),
        (None, "> 100m",   []),
    ]

    for row_num, dist_m in outside_polygon:
        for threshold, _, bucket in buckets:
            if threshold is None or dist_m < threshold:
                bucket.append(row_num)
                break

    total   = len(outside_polygon)
    lines   = [f"{total} pixel(s) have footprint outside plot shape boundary:"]

    for _, label, bucket in buckets:
        if not bucket:
            continue
        sample = bucket[:5]
        extra  = len(bucket) - 5
        suffix = f" (and {extra} more)" if extra > 0 else ""
        rows   = ", ".join(str(r) for r in sample)
        lines.append(f"  {label}: {len(bucket)} pixel(s) at rows: {rows}{suffix}")

    return [{"file": "spectra", "row": None, "column": None, "message": "\n".join(lines)}]


def _summarise_coord_errors(row_numbers: list[int], description: str) -> list[dict]:
    """
    Collapse a list of row numbers into a single summary error message,
    showing the first five affected rows and a count of the rest.
    """
    if not row_numbers:
        return []
    sample = row_numbers[:5]
    extra  = len(row_numbers) - 5
    suffix = f" (and {extra} more)" if extra > 0 else ""
    return [{
        "file": "spectra", "row": None, "column": None,
        "message": (
            f"{len(row_numbers)} {description} at rows: "
            f"{', '.join(str(r) for r in sample)}{suffix}"
        ),
    }]

