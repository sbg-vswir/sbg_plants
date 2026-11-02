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
       c. Granule sensor — the row's campaign_name / sensor_name must match
                           its granule's.
          Band count — number of band columns must match the wavelength count
                       of the granule's sensor calibration (campaign, sensor,
                       sensor_date), looked up through granule_id.
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
from pyproj import Transformer, CRS
from shapely.ops import transform

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import (
    load_config, run_mechanical_checks,
    check_required_columns, check_no_missing_values,
    check_castable, check_extra_columns, normalize,
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
    all_plots, all_shape_map, all_band_counts, all_gsd_map, all_granule_sensors = _build_reference_sets(context)

    errors          = []
    warnings        = []
    pk_seen         = set()
    out_of_bounds        = []   # row numbers where lon/lat are outside WGS84 range
    outside_polygon      = []   # (row_number, distance_m) — footprint also misses
    centroid_only_misses = []   # (row_number, distance_m) — centroid outside but footprint overlaps

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

        errors += _check_granule_sensor(
            campaign, sensor, granule, band_cols, all_granule_sensors, all_band_counts, idx,
        )

        pk = (campaign, plot, granule, normalize(row["glt_row"], "int"), normalize(row["glt_column"], "int"))
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

        row_out_of_bounds, row_outside_polygon, row_centroid_only = _check_coordinates(
            row, all_shape_map[int_key], all_gsd_map.get(granule), idx
        )
        out_of_bounds        += row_out_of_bounds
        outside_polygon      += row_outside_polygon
        centroid_only_misses += row_centroid_only

    errors   += _summarise_coord_errors(
        out_of_bounds,
        "pixel(s) have lon/lat outside WGS84 bounds (-180..180, -90..90)",
    )
    warnings += _summarise_outside_polygon(outside_polygon)
    warnings += _summarise_outside_polygon(
        centroid_only_misses,
        label="center outside plot shape but footprint overlaps (edge pixels)",
    )

    return errors, warnings


def _build_reference_sets(context: CheckContext) -> tuple[set, dict, dict, dict, dict]:
    """Merge bundle and DB reference sets for plot FK, shape, band count, GSD and granule sensor lookups."""
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
    all_granule_sensors = {
        **context.db["granule_sensor_map"],
        **context.output.get("granule_sensor_map", {}),
    }
    return all_plots, all_shape_map, all_band_counts, all_gsd_map, all_granule_sensors


def _check_granule_sensor(
    campaign: str,
    sensor: str,
    granule: str,
    band_cols: list[int],
    all_granule_sensors: dict,
    all_band_counts: dict,
    idx: int,
) -> list[dict]:
    """
    The row's campaign/sensor must match its granule's, and the number of band
    columns must match the wavelength count of the granule's calibration.
    A granule that resolves nowhere is already reported by the intersect check.
    """
    sensor_key = all_granule_sensors.get(granule)
    if sensor_key is None:
        return []
    if (campaign, sensor) != sensor_key[:2]:
        return [{
            "file": "spectra", "row": int(idx + 2), "column": "sensor_name",
            "message": (
                f"(campaign_name='{campaign}', sensor_name='{sensor}') does not match "
                f"granule '{granule}' ({sensor_key[0]}, {sensor_key[1]})"
            ),
        }]
    expected = all_band_counts.get(sensor_key)
    if expected is not None and len(band_cols) != expected:
        return [{
            "file": "spectra", "row": int(idx + 2), "column": None,
            "message": (
                f"band column count ({len(band_cols)}) does not match "
                f"wavelength count ({expected}) for {sensor_key}"
            ),
        }]
    return []

def _check_coordinates(
    row: pd.Series,
    plot_geom,
    gsd: float | None,
    idx: int,
) -> tuple[list[int], list[tuple[int, float]], list[tuple[int, float]]]:
    """
    Check lon/lat for WGS84 bounds and pixel intersection with the plot shape.
    Returns (out_of_bounds_rows, outside_polygon_entries, centroid_only_miss_entries).

    When GSD is known, always runs both checks:
      - Point-in-polygon: centroid must be inside the plot
      - Footprint-in-polygon: GSD×GSD square centred on centroid must intersect

    Cases:
      Point ✓               → passes, neither list populated
      Point ✗, Footprint ✓  → edge pixel; goes into centroid_only_miss_entries
      Point ✗, Footprint ✗  → clearly outside; goes into outside_polygon_entries

    When GSD is unknown, only the point check is run (outside_polygon_entries).

    Distances are computed in a local azimuthal equidistant projection to avoid
    the latitude-dependent degree-to-metre error of a flat approximation.
    """
    try:
        lon = float(row["lon"])
        lat = float(row["lat"])
    except (ValueError, TypeError):
        return [], [], []

    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return [idx + 2], [], []

    pt = Point(lon, lat)

    # Build a local azimuthal equidistant CRS centred on this point.
    aeqd = CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m"
    )
    to_aeqd  = Transformer.from_crs("EPSG:4326", aeqd, always_xy=True).transform
    to_wgs84 = Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True).transform

    point_intersects = plot_geom.intersects(pt)

    if point_intersects:
        return [], [], []

    # Centroid is outside — compute distance for bucketing.
    plot_geom_proj = transform(to_aeqd, plot_geom)
    dist_m = plot_geom_proj.exterior.distance(transform(to_aeqd, pt))

    if gsd is not None:
        pt_proj        = transform(to_aeqd, pt)
        half           = float(gsd) / 2
        footprint_proj = pt_proj.buffer(half, cap_style=3)   # square, metres
        pixel_footprint = transform(to_wgs84, footprint_proj)
        footprint_intersects = plot_geom.intersects(pixel_footprint)
        if footprint_intersects:
            # Edge pixel — centroid outside but footprint overlaps
            return [], [], [(idx + 2, dist_m)]
        else:
            # Clearly outside
            return [], [(idx + 2, dist_m)], []
    else:
        # No GSD — only point check available
        return [], [(idx + 2, dist_m)], []

# if gsd is in degrees
# def _check_coordinates(
#     row: pd.Series,
#     plot_geom,
#     gsd: float | None,
#     idx: int,
# ) -> tuple[list[int], list[tuple[int, float]]]:
#     """
#     Check lon/lat for WGS84 bounds and pixel footprint intersection.
#     Returns (out_of_bounds_rows, outside_polygon_entries).

#     GSD is expected in degrees.
#     """
#     try:
#         lon = float(row["lon"])
#         lat = float(row["lat"])
#     except (ValueError, TypeError):
#         return [], []

#     if not (-180 <= lon <= 180 and -90 <= lat <= 90):
#         return [idx + 2], []

#     pt = Point(lon, lat)

#     if gsd is not None:
#         half = float(gsd) / 2
#         pixel_footprint = pt.buffer(half, cap_style=3)
#         intersects = plot_geom.intersects(pixel_footprint)
#     else:
#         intersects = plot_geom.intersects(pt)

#     if not intersects:
#         dist_deg = plot_geom.exterior.distance(pt)
#         return [], [(idx + 2, dist_deg)]

#     return [], []


def _summarise_outside_polygon(
    outside_polygon: list[tuple[int, float]],
    label: str = "footprint outside plot shape boundary",
) -> list[dict]:
    """
    Summarise pixel intersection violations bucketed by distance from the polygon
    boundary. Helps distinguish reprojection artefacts (< 1m) from genuine
    data errors (> 10m).
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

    total = len(outside_polygon)
    lines = [f"{total} pixel(s) have {label}:"]

    for _, bucket_label, bucket in buckets:
        if not bucket:
            continue
        sample = bucket[:5]
        extra  = len(bucket) - 5
        suffix = f" (and {extra} more)" if extra > 0 else ""
        rows   = ", ".join(str(r) for r in sample)
        lines.append(f"  {bucket_label}: {len(bucket)} pixel(s) at rows: {rows}{suffix}")

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

