"""
QAQC checks for plots.geojson

Checks (in order):
  1. GeoDataFrame structure — must be non-empty and have a geometry column.
  2. Per feature (row):
       a. Geometry — must be a Polygon, topologically valid, within WGS84
                     bounds, non-zero area.
       b. Required properties — all declared required_props must be present.
       c. Enum properties — declared enum_props values must be valid.
       d. Extra property warning — unexpected properties flagged.
       e. Granule FK — granule_id must resolve to this bundle or the DB.
       f. Uniqueness — (campaign_name, plot_name, granule_id) must be unique
                       within the file and must not already exist in the DB.
  3. Existing plot warning — (campaign_name, plot_name) already in production
                             plot table. Not an error since plots are reused
                             across granules (ON CONFLICT DO NOTHING).
  4. Forward plot_shape_map and plot_id_map for traits.py and spectra.py.

Config (checks/config/plots.json) declares required_props, nullable_props,
and enum_props since this file is GeoJSON, not a CSV.

NOTE: context.data["plots"] is a GeoDataFrame (see app.checks.io). All
non-geometry columns were coerced to string and nulls filled with "" at
parse time, so this file treats both None and "" as "blank" throughout —
there is no longer a real None sentinel coming out of the source data.
"""

from __future__ import annotations

import geopandas as gpd
from shapely.validation import make_valid

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import load_config

CONFIG = load_config("plots")

# Minimum properties needed to build a valid (campaign_name, plot_name)
# FK key for plot_id_map / plot_shape_map. If any of these are missing or
# blank, the plot cannot be registered at all — but a missing prop outside
# this set (e.g. polygon_confidence) should still be reported as its own
# error without blocking registration, so downstream FK checks in
# spectra.py/traits.py don't cascade misleading "not found" errors.
CORE_PROPS = ["campaign_name", "plot_name", "site_id", "granule_id"]


def _is_blank(val) -> bool:
    """True if val is None, NaN, or an empty/whitespace-only string."""
    if val is None:
        return True
    try:
        if val != val:  # NaN
            return True
    except Exception:
        pass
    return isinstance(val, str) and val.strip() == ""


def check(context: CheckContext) -> CheckResult:
    gdf_plots = context.data["plots"]
    geom_col  = gdf_plots.geometry.name

    errors, warnings = _check_geodataframe_structure(gdf_plots)
    if errors:
        return CheckResult("plots", 0, errors, warnings)

    plot_shape_map = {}
    plot_id_map    = {}
    seen_intersect_keys = set()
    skipped_core_missing = 0

    all_granule_ids = (
        context.output.get("granule_id_set", set())
        | context.db["granule_ids"]
    )

    for i, (_, row) in enumerate(gdf_plots.iterrows()):
        feat_num = i + 1  # 1-based for error reporting

        geom, geom_errors = _check_geometry(row, geom_col, feat_num)
        errors += geom_errors
        if geom is None:
            continue  # can't check properties without a valid geometry

        prop_errors, prop_warnings, props = _check_properties(
            row, geom_col, feat_num, context.enums
        )
        errors   += prop_errors
        warnings += prop_warnings
        if props is None:
            skipped_core_missing += 1
            continue  # missing core identity props — cannot build FK key

        fk_errors, intersect_key = _check_feature_fk_and_uniqueness(
            props, feat_num, all_granule_ids,
            seen_intersect_keys, context.db["plot_intersect_set"],
        )
        errors += fk_errors
        seen_intersect_keys.add(intersect_key)

        plot_shape_map[intersect_key] = geom
        if (props["campaign_name"], props["plot_name"]) not in plot_id_map:
            plot_id_map[(props["campaign_name"], props["plot_name"])] = {
                "site_id":     props["site_id"],
                "plot_method": props.get("plot_method"),
            }

    if skipped_core_missing:
        n = len(gdf_plots)
        warnings.append(_e(
            None,
            f"{skipped_core_missing}/{n} plot feature"
            f"{'s' if skipped_core_missing != 1 else ''} skipped from FK "
            f"matching due to missing/blank core properties "
            f"({', '.join(CORE_PROPS)})",
        ))

    _forward_plot_maps(plot_shape_map, plot_id_map, context)
    errors  += _check_existing_plots(plot_id_map, context)
    return CheckResult("plots", len(gdf_plots), errors, warnings)


# ── Structural check ───────────────────────────────────────────────────────────

def _check_geodataframe_structure(gdf_plots: gpd.GeoDataFrame) -> tuple[list[dict], list[dict]]:
    """Plots GeoDataFrame must be non-empty and carry a geometry column."""
    if gdf_plots is None or gdf_plots.empty:
        return [_e(None, "plots file has no features")], []
    if gdf_plots.geometry.name not in gdf_plots.columns:
        return [_e(None, "plots file has no geometry column")], []
    return [], []


# ── Per-feature checks ─────────────────────────────────────────────────────────

def _check_geometry(row, geom_col: str, feat_num: int) -> tuple:
    """
    Validate a row's geometry (already a shapely object via geopandas).
    Returns (shapely_geometry, errors).
    Returns (None, errors) if the geometry is unusable.
    """
    geom   = row[geom_col]
    errors = []

    if geom is None or geom.is_empty:
        return None, [_e(feat_num, "geometry is missing or empty")]

    if geom.geom_type != "Polygon":
        return None, [_e(feat_num, "geometry must be a Polygon")]

    minx, miny, maxx, maxy = geom.bounds
    if not (-180 <= minx <= 180 and -180 <= maxx <= 180 and
            -90  <= miny <= 90  and -90  <= maxy <= 90):
        errors.append(_e(feat_num, "coordinates outside WGS84 bounds (EPSG:4326 expected)"))

    if not geom.is_valid:
        geom = make_valid(geom)
        if not geom.is_valid:
            errors.append(_e(feat_num, "polygon is not topologically valid"))

    if geom.area == 0:
        errors.append(_e(feat_num, "polygon has zero area"))

    return geom, errors


def _check_properties(
    row,
    geom_col: str,
    feat_num: int,
    enums: dict,
) -> tuple[list[dict], list[dict], dict | None]:
    """
    Validate a row's properties (all columns except geometry) against config.
    Returns (errors, warnings, props_dict).
    Returns (errors, warnings, None) only if a *core* identity property
    (see CORE_PROPS) is missing/blank — those are needed to build the
    (campaign_name, plot_name) FK key, so callers must skip FK/uniqueness
    checks and registration in that case.

    A missing/blank *non-core* required property (e.g. polygon_confidence)
    is still reported as an error here, but does NOT block registering the
    plot in plot_id_map/plot_shape_map — otherwise a single unrelated
    missing property on the plots file would cascade into misleading
    "not found in plots.geojson or database" errors for every spectra/traits
    row referencing that plot.
    """
    props          = row.drop(labels=[geom_col]).to_dict()
    required_props = CONFIG.get("required_props", [])
    nullable_props = CONFIG.get("nullable_props", [])
    enum_props     = CONFIG.get("enum_props", {})
    all_known      = set(required_props) | set(nullable_props)

    errors   = []
    warnings = []

    missing = [p for p in required_props if p not in props or _is_blank(props[p])]
    if missing:
        errors.append(_e(feat_num, f"missing required properties: {', '.join(missing)}"))

    missing_core = [p for p in CORE_PROPS if p not in props or _is_blank(props[p])]
    if missing_core:
        return errors, [], None

    for prop, enum_type in enum_props.items():
        val = props.get(prop)
        if not _is_blank(val) and val not in enums.get(enum_type, set()):
            errors.append(_e(
                feat_num,
                f"'{val}' is not a valid value for '{prop}' "
                f"(valid: {sorted(enums.get(enum_type, set()))})",
                column=prop,
            ))

    extra = [p for p in props if p not in all_known]
    if extra:
        warnings.append(_e(
            feat_num,
            f"unexpected {'properties' if len(extra) > 1 else 'property'} "
            f"not in schema: {', '.join(sorted(extra))}",
        ))

    # Blank ("" or NaN, since the source data was pre-stringified) becomes
    # None so downstream code can rely on a single "missing" sentinel again.
    normalised = {k: (None if _is_blank(v) else v) for k, v in props.items()}
    return errors, warnings, normalised


def _check_feature_fk_and_uniqueness(
    props: dict,
    feat_num: int,
    all_granule_ids: set,
    seen_intersect_keys: set,
    db_plot_intersect_set: set,
) -> tuple[list[dict], tuple]:
    """
    Check that:
      - granule_id resolves to this bundle or the DB
      - (campaign_name, plot_name, granule_id) is unique within the file
      - (campaign_name, plot_name, granule_id) does not already exist in the DB
    Returns (errors, intersect_key).
    """
    campaign_name = props["campaign_name"]
    plot_name     = props["plot_name"]
    granule_id    = props["granule_id"]
    intersect_key = (campaign_name, plot_name, granule_id)
    errors        = []

    if granule_id not in all_granule_ids:
        errors.append(_e(
            feat_num,
            f"granule_id '{granule_id}' not found in bundle or database",
            column="granule_id",
        ))

    if intersect_key in seen_intersect_keys:
        errors.append(_e(
            feat_num,
            f"duplicate (campaign_name, plot_name, granule_id) = {intersect_key}",
        ))

    if intersect_key in db_plot_intersect_set:
        errors.append(_e(
            feat_num,
            f"plot-granule intersection {intersect_key} already exists in database",
        ))

    return errors, intersect_key


# ── Forwarded output ───────────────────────────────────────────────────────────

def _check_existing_plots(plot_id_map: dict, context: CheckContext) -> list[dict]:
    """
    Error when a (campaign_name, plot_name) from the bundle already exists in
    the production plot table. Plots cannot be re-ingested — each plot must be
    unique in production.
    """
    errors = []
    for (campaign_name, plot_name) in plot_id_map:
        if (campaign_name, plot_name) in context.db["plot_set"]:
            errors.append(_e(
                None,
                f"(campaign_name='{campaign_name}', plot_name='{plot_name}') "
                f"already exists in database",
            ))
    return errors


def _forward_plot_maps(
    plot_shape_map: dict,
    plot_id_map: dict,
    context: CheckContext,
) -> None:
    """
    Write plot_shape_map and plot_id_map into context for traits.py and spectra.py.

    plot_shape_map: { (campaign_name, plot_name, granule_id): shapely_geometry }
    plot_id_map:    { (campaign_name, plot_name): { site_id, plot_method } }
    """
    context.output["plot_shape_map"] = plot_shape_map
    context.output["plot_id_map"]    = plot_id_map


# ── Error helper ───────────────────────────────────────────────────────────────

def _e(feat_num: int | None, message: str, column: str | None = None) -> dict:
    return {"file": "plots", "row": feat_num, "column": column, "message": message}