"""
orchestration.py — 4-stage linked plot / trait / granule query.

Stage 1 : Spatial filter on plot_shape_view → all matching plot_ids + total_plots
Stage 2 : Parallel COUNT queries (two separate DB connections) → total_traits,
          total_granules.  No data rows fetched yet.
Stage 3 : Paginate plot_ids → plot_ids_page[offset:offset+limit]
Stage 4 : Parallel data queries for the page only (two separate DB connections):
            4a — plot geometries   (plot_shape_view)
            4b — trait rows        (trait_view)
            4c — granule rows      (granule_view CTE → pixel JOIN → array_agg)

Granule queries use a CTE so the planner narrows granules BEFORE joining pixels.
All filter clause building goes through build_where_clause / _build_array_in_clause
— no hand-rolled SQL predicates.
"""

import logging
import io
import base64
import concurrent.futures
import shapely.geometry
import shapely.wkt

import geopandas as gpd
import pandas as pd

from app.db import get_connection
from app.filter import build_where_clause
from app.filter_utils import _build_array_in_clause

logger = logging.getLogger("lambda_handler")

# ---------------------------------------------------------------------------
# Date alias remapping
# ---------------------------------------------------------------------------

_TRAIT_DATE_ALIASES = {
    "collection_date_start": "start_date",
    "collection_date_end":   "end_date",
}

_GRANULE_DATE_ALIASES = {
    "acquisition_date_start": "start_date",
    "acquisition_date_end":   "end_date",
}


def _remap_date_aliases(filters: dict, alias_map: dict) -> dict:
    """Return a copy of *filters* with date alias keys replaced by canonical names."""
    return {alias_map.get(k, k): v for k, v in filters.items()}


# ---------------------------------------------------------------------------
# Shared WHERE-clause builders
# ---------------------------------------------------------------------------

def _trait_where(trait_filters: dict, plot_ids: list):
    """
    Build WHERE clause + params for trait_view scoped to plot_ids.
    plot_id uses the 'array' type so build_where_clause emits plot_id = ANY(%s).
    """
    filters = _remap_date_aliases(dict(trait_filters or {}), _TRAIT_DATE_ALIASES)
    filters["plot_id"] = plot_ids
    return build_where_clause("trait_view", filters)


def _granule_cte_and_where(granule_filters: dict, plot_ids: list):
    """
    Return (cte_sql, where_sql, params) for the granule+pixel aggregation query.

    The CTE narrows granule_view by any granule-column filters BEFORE the pixel
    JOIN, so the planner touches only the relevant granule rows first.

    pixel-side filter (px.plot_id = ANY(%s)) is appended after the CTE.
    """
    # Build granule-column WHERE via build_where_clause
    granule_fragment = ""
    granule_params: tuple = ()
    if granule_filters:
        remapped = _remap_date_aliases(granule_filters, _GRANULE_DATE_ALIASES)
        granule_where, granule_params = build_where_clause("granule_view", remapped)
        if granule_where:
            granule_fragment = granule_where.lstrip().removeprefix("WHERE").strip()

    cte_sql = f"""
        WITH filtered_granules AS (
            SELECT
                granule_id,
                campaign_name,
                sensor_name,
                acquisition_date,
                acquisition_start_time,
                cloudy_conditions,
                cloud_type
            FROM vswir_plants.granule_view
            {"WHERE " + granule_fragment if granule_fragment else ""}
        )"""

    # pixel-side clause
    px_clauses = []
    px_params  = []
    _build_array_in_clause("plot_id", plot_ids, px_clauses, px_params)
    pixel_fragment = px_clauses[0].replace('"plot_id"', 'px.plot_id')

    # combined params: granule params bind into the CTE, pixel params into WHERE
    params = list(granule_params) + px_params

    return cte_sql, pixel_fragment, params


# ---------------------------------------------------------------------------
# Stage 1 — spatial filter
# ---------------------------------------------------------------------------

def _stage1_plot_ids(geojson, campaign_name, conn):
    """
    Return all plot_ids matching the spatial + campaign filters.
    Cheap: returns only integers via the GIST index on plot_shape.
    """
    filters = {}
    if campaign_name:
        filters["campaign_name"] = campaign_name
    if geojson:
        filters["geom"] = geojson

    where_clause, where_params = build_where_clause("plot_shape_view", filters)
    sql = f"SELECT DISTINCT plot_id FROM vswir_plants.plot_shape_view{where_clause}"
    logger.debug("Stage 1 SQL: %s", sql)

    df = pd.read_sql(sql, conn, params=list(where_params))
    return df["plot_id"].tolist()


def _plot_ids_with_traits(plot_ids, trait_filters):
    """
    Narrow plot_ids to only those that have at least one matching trait row.
    Opens its own connection.
    """
    where_clause, where_params = _trait_where(trait_filters, plot_ids)
    sql = f"SELECT DISTINCT plot_id FROM vswir_plants.trait_view{where_clause}"
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=list(where_params))
    return df["plot_id"].tolist()


def _plot_ids_with_granules(plot_ids, granule_filters):
    """
    Narrow plot_ids to only those that have at least one matching granule (via pixel).
    Opens its own connection.
    """
    cte_sql, pixel_fragment, params = _granule_cte_and_where(granule_filters, plot_ids)
    sql = f"""
        {cte_sql}
        SELECT DISTINCT px.plot_id
        FROM filtered_granules fg
        JOIN vswir_plants.pixel px ON px.granule_id = fg.granule_id
        WHERE {pixel_fragment}
    """
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=params)
    return df["plot_id"].tolist()


# ---------------------------------------------------------------------------
# Stage 2 — parallel COUNT queries (separate connections, no data rows)
# ---------------------------------------------------------------------------

def _count_traits(plot_ids, trait_filters):
    """COUNT(*) on trait_view for all matching plots — opens its own connection."""
    where_clause, where_params = _trait_where(trait_filters, plot_ids)
    sql = f"SELECT COUNT(*) AS n FROM vswir_plants.trait_view{where_clause}"
    logger.debug("Count traits SQL: %s", sql)
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=list(where_params))
    return int(df["n"].iloc[0])


def _count_granules(plot_ids, granule_filters):
    """
    COUNT(DISTINCT granule_id) via the CTE pattern — opens its own connection.
    Narrows granules first, then counts distinct granule_ids that have pixels
    for the matched plots.
    """
    cte_sql, pixel_fragment, params = _granule_cte_and_where(granule_filters, plot_ids)
    sql = f"""
        {cte_sql}
        SELECT COUNT(DISTINCT fg.granule_id) AS n
        FROM filtered_granules fg
        JOIN vswir_plants.pixel px ON px.granule_id = fg.granule_id
        WHERE {pixel_fragment}
    """
    logger.debug("Count granules SQL: %s", sql)
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=params)
    return int(df["n"].iloc[0])


# ---------------------------------------------------------------------------
# Stage 4 — parallel data queries for the page (separate connections)
# ---------------------------------------------------------------------------

def _fetch_plots(plot_ids_page, fmt):
    """
    Fetch plot_shape_view rows for the page and serialise to the requested format.
    Opens its own connection.
    """
    if not plot_ids_page:
        return {}

    clauses = []
    params  = []
    _build_array_in_clause("plot_id", plot_ids_page, clauses, params)
    where = " WHERE " + clauses[0]
    sql = f"SELECT * FROM vswir_plants.plot_shape_view{where}"

    with get_connection() as conn:
        try:
            df = gpd.read_postgis(sql, conn, geom_col="geom", params=params)
        except Exception:
            df = pd.read_sql(sql, conn, params=params)

    if fmt == "geoparquet" and "geom" in df.columns:
        if not isinstance(df, gpd.GeoDataFrame):
            df["geom"] = df["geom"].apply(
                lambda g: shapely.wkt.loads(g) if isinstance(g, str) else g
            )
            df = gpd.GeoDataFrame(df, geometry="geom", crs="EPSG:4326")
        buf = io.BytesIO()
        df.to_parquet(buf, index=False, engine="pyarrow")
        return {"plots_geoparquet": base64.b64encode(buf.getvalue()).decode()}

    if fmt in ("json", "geojson") and "geom" in df.columns:
        features = []
        for _, row in df.iterrows():
            geom = row["geom"]
            if isinstance(geom, str):
                geom = shapely.wkt.loads(geom)
            props = {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                     for k, v in row.drop("geom").items()}
            features.append({
                "type": "Feature",
                "geometry": shapely.geometry.mapping(geom) if geom else None,
                "properties": props,
            })
        return {"plots_geojson": {"type": "FeatureCollection", "features": features}}

    records = df.to_dict(orient="records")
    for row in records:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
    return {"plots": records}


def _fetch_traits(plot_ids_page, trait_filters):
    """
    Fetch trait rows for the page only. Opens its own connection.
    """
    if not plot_ids_page:
        return []

    where_clause, where_params = _trait_where(trait_filters, plot_ids_page)
    sql = f"SELECT * FROM vswir_plants.trait_view{where_clause}"
    logger.debug("Fetch traits SQL: %s", sql)

    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=list(where_params))
    return df.to_dict(orient="records")


def _fetch_granules(plot_ids_page, granule_filters):
    """
    Fetch granule rows with aggregated pixel_ids for the page only.

    CTE narrows granule_view by granule-column filters first, then joins
    pixel scoped to plot_ids_page — aggregation only runs on the narrow set.
    Opens its own connection.
    """
    if not plot_ids_page:
        return []

    cte_sql, pixel_fragment, params = _granule_cte_and_where(granule_filters, plot_ids_page)

    sql = f"""
        {cte_sql}
        SELECT
            fg.granule_id,
            fg.campaign_name,
            fg.sensor_name,
            fg.acquisition_date,
            fg.acquisition_start_time,
            fg.cloudy_conditions,
            fg.cloud_type,
            array_agg(DISTINCT px.plot_id)              AS plot_ids,
            array_agg(px.pixel_id ORDER BY px.pixel_id) AS pixel_ids
        FROM filtered_granules fg
        JOIN vswir_plants.pixel px ON px.granule_id = fg.granule_id
        WHERE {pixel_fragment}
        GROUP BY
            fg.granule_id, fg.campaign_name, fg.sensor_name,
            fg.acquisition_date, fg.acquisition_start_time,
            fg.cloudy_conditions, fg.cloud_type
    """
    logger.debug("Fetch granules SQL: %s", sql)

    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=params)

    # Ensure arrays are Python lists
    for col in ("plot_ids", "pixel_ids"):
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: list(v) if hasattr(v, "__iter__") and not isinstance(v, str) else v
            )

    records = []
    for row in df.to_dict(orient="records"):
        for key, val in row.items():
            if hasattr(val, "isoformat"):
                row[key] = val.isoformat()
        records.append(row)

    return records


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_linked_query(body: dict) -> dict:
    """
    Execute the 4-stage linked query and return the assembled response body.

    Stage 1 : Spatial filter → all matching plot_ids (single connection, cheap)
    Stage 2 : Parallel COUNT queries (two connections) → total_traits, total_granules
    Stage 3 : Paginate plot_ids
    Stage 4 : Parallel data queries for page only (three connections) →
              plots, traits, granules

    Parameters (all optional):
        campaign_name   : str
        geojson         : GeoJSON geometry dict
        trait_filters   : dict  — trait/sample/date filters
        granule_filters : dict  — sensor/date filters
        format          : str   — 'geoparquet' | 'geojson' | 'json'
        limit           : int   — plots per page (default 100)
        offset          : int   — plot page offset (default 0)
    """
    campaign_name   = body.get("campaign_name")
    geojson         = body.get("geojson")
    trait_filters   = body.get("trait_filters") or {}
    granule_filters = body.get("granule_filters") or {}
    fmt             = (body.get("format") or "json").lower()
    limit           = int(body.get("limit", 100))
    offset          = int(body.get("offset", 0))

    # ------------------------------------------------------------------
    # Stage 1 — spatial filter (single connection)
    # ------------------------------------------------------------------
    with get_connection() as conn:
        all_plot_ids = _stage1_plot_ids(geojson, campaign_name, conn)

    # Stage 1b — if trait or granule filters are provided, narrow plot_ids
    # to only those that actually have matching traits / granules.
    # Run in parallel when both filters are active.
    if trait_filters and granule_filters:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            tf = pool.submit(_plot_ids_with_traits,   all_plot_ids, trait_filters)
            gf = pool.submit(_plot_ids_with_granules, all_plot_ids, granule_filters)
            trait_plot_ids   = set(tf.result())
            granule_plot_ids = set(gf.result())
        all_plot_ids = [p for p in all_plot_ids if p in trait_plot_ids and p in granule_plot_ids]
    elif trait_filters:
        trait_plot_ids = set(_plot_ids_with_traits(all_plot_ids, trait_filters))
        all_plot_ids = [p for p in all_plot_ids if p in trait_plot_ids]
    elif granule_filters:
        granule_plot_ids = set(_plot_ids_with_granules(all_plot_ids, granule_filters))
        all_plot_ids = [p for p in all_plot_ids if p in granule_plot_ids]

    total_plots = len(all_plot_ids)

    if not all_plot_ids:
        return {
            "total_plots":    0,
            "total_traits":   0,
            "total_granules": 0,
            "truncated":      False,
            "plots":          [],
            "traits":         [],
            "granules":       [],
        }

    # ------------------------------------------------------------------
    # Stage 2 — parallel COUNT queries (two separate connections)
    # Counts are over the full matched plot set so pagination totals are accurate.
    # ------------------------------------------------------------------
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        trait_count_future   = pool.submit(_count_traits,   all_plot_ids, trait_filters)
        granule_count_future = pool.submit(_count_granules, all_plot_ids, granule_filters)
        total_traits   = trait_count_future.result()
        total_granules = granule_count_future.result()

    # ------------------------------------------------------------------
    # Stage 3 — paginate plot list
    # ------------------------------------------------------------------
    truncated     = total_plots > (offset + limit)
    plot_ids_page = all_plot_ids[offset: offset + limit]

    # ------------------------------------------------------------------
    # Stage 4 — parallel data queries for the page only (three connections)
    # ------------------------------------------------------------------
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        plots_future   = pool.submit(_fetch_plots,   plot_ids_page, fmt)
        traits_future  = pool.submit(_fetch_traits,  plot_ids_page, trait_filters)
        granules_future = pool.submit(_fetch_granules, plot_ids_page, granule_filters)
        plots_payload = plots_future.result()
        page_traits   = traits_future.result()
        page_granules = granules_future.result()

    logger.debug(
        "Linked query: %d plots total (%d traits, %d granules), page %d-%d",
        total_plots, total_traits, total_granules, offset, offset + limit,
    )

    response = {
        "total_plots":    total_plots,
        "total_traits":   total_traits,
        "total_granules": total_granules,
        "truncated":      truncated,
        "traits":         page_traits,
        "granules":       page_granules,
    }
    response.update(plots_payload)
    return response
