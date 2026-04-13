"""
QAQC checks for plots.geojson

Checks (in order):
  1. GeoJSON structure — must be a FeatureCollection with at least one feature.
  2. Per feature:
       a. Geometry — must be a Polygon or Point, parseable, topologically valid,
                     within WGS84 bounds, non-zero area (Polygons only).
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
"""

from __future__ import annotations

from shapely.geometry import shape
from shapely.validation import make_valid

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import load_config

CONFIG = load_config("plots")


def check(context: CheckContext) -> CheckResult:
    geojson  = context.data["plots"]
    features = geojson.get("features", [])

    errors, warnings = _check_geojson_structure(geojson)
    if errors:
        return CheckResult("plots", 0, errors, warnings)

    plot_shape_map = {}
    plot_id_map    = {}
    seen_intersect_keys = set()

    all_granule_ids = (
        context.output.get("granule_id_set", set())
        | context.db["granule_ids"]
    )

    for i, feature in enumerate(features):
        feat_num = i + 1  # 1-based for error reporting

        geom, geom_errors = _check_geometry(feature, feat_num)
        errors += geom_errors
        if geom is None:
            continue  # can't check properties without a valid geometry

        prop_errors, prop_warnings, props = _check_properties(
            feature, feat_num, context.enums
        )
        errors   += prop_errors
        warnings += prop_warnings
        if props is None:
            continue  # missing required props — skip FK/uniqueness checks

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

    _forward_plot_maps(plot_shape_map, plot_id_map, context)
    warnings += _warn_existing_plots(plot_id_map, context)
    return CheckResult("plots", len(features), errors, warnings)


# ── Structural check ───────────────────────────────────────────────────────────

def _check_geojson_structure(geojson: dict) -> tuple[list[dict], list[dict]]:
    """Top-level GeoJSON must be a FeatureCollection with at least one feature."""
    if geojson.get("type") != "FeatureCollection":
        return [_e(None, "must be a GeoJSON FeatureCollection")], []
    if not geojson.get("features"):
        return [_e(None, "FeatureCollection has no features")], []
    return [], []


# ── Per-feature checks ─────────────────────────────────────────────────────────

def _check_geometry(feature: dict, feat_num: int) -> tuple:
    """
    Parse and validate feature geometry.
    Returns (shapely_geometry, errors).
    Returns (None, errors) if the geometry is unusable.
    """
    geom_raw = feature.get("geometry")
    errors   = []

    if not geom_raw or geom_raw.get("type") != "Polygon":
        return None, [_e(feat_num, "geometry must be a Polygon")]

    try:
        geom = shape(geom_raw)
    except Exception as exc:
        return None, [_e(feat_num, f"invalid geometry — {exc}")]

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
    feature: dict,
    feat_num: int,
    enums: dict,
) -> tuple[list[dict], list[dict], dict | None]:
    """
    Validate feature properties against the config.
    Returns (errors, warnings, props_dict).
    Returns (errors, warnings, None) if required properties are missing —
    callers should skip FK and uniqueness checks in that case.
    """
    props          = feature.get("properties") or {}
    required_props = CONFIG.get("required_props", [])
    nullable_props = CONFIG.get("nullable_props", [])
    enum_props     = CONFIG.get("enum_props", {})
    all_known      = set(required_props) | set(nullable_props)

    errors   = []
    warnings = []

    missing = [p for p in required_props if p not in props or props[p] is None]
    if missing:
        return [_e(feat_num, f"missing required properties: {', '.join(missing)}")], [], None

    for prop, enum_type in enum_props.items():
        val = props.get(prop)
        if val is not None and val not in enums.get(enum_type, set()):
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

    # Normalise the values callers will use
    normalised = {k: str(v) if v is not None else v for k, v in props.items()}
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

def _warn_existing_plots(plot_id_map: dict, context: CheckContext) -> list[dict]:
    """
    Warn when a (campaign_name, plot_name) from the bundle already exists in
    the production plot table. This is not an error — plots are reused across
    granules and the staging insert uses ON CONFLICT DO NOTHING. It is worth
    flagging so the submitter is aware their plot geometries will be compared
    against the existing production record.
    """
    warnings = []
    for (campaign_name, plot_name) in plot_id_map:
        if (campaign_name, plot_name) in context.db["plot_set"]:
            warnings.append(_e(
                None,
                f"(campaign_name='{campaign_name}', plot_name='{plot_name}') "
                f"already exists in database — existing plot record will be reused",
            ))
    return warnings


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
