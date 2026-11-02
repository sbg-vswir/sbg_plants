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

The 'schema' parameter accepted by run_linked_query (and threaded through all
internal helpers) is a fully-qualified PostgreSQL schema name, e.g.:
    "vswir_plants"          → production
    "vswir_plants_staging"  → staging (admin+ only)
Both are served by the same DB user (postgrest_user) which has SELECT on both.
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
    filters = _remap_date_aliases(dict(trait_filters or {}), _TRAIT_DATE_ALIASES)
    filters["plot_id"] = plot_ids
    return build_where_clause("trait_view", filters)


def _granule_cte_and_where(granule_filters: dict, plot_ids: list, schema: str):
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
                sensor_date,
                acquisition_date,
                acquisition_start_time,
                cloudy_conditions,
                cloud_type
            FROM "{schema}".granule_view
            {"WHERE " + granule_fragment if granule_fragment else ""}
        )"""

    px_clauses = []
    px_params  = []
    _build_array_in_clause("plot_id", plot_ids, px_clauses, px_params)
    pixel_fragment = px_clauses[0].replace('"plot_id"', 'px.plot_id')

    params = list(granule_params) + px_params
    return cte_sql, pixel_fragment, params


# ---------------------------------------------------------------------------
# Stage 1 — spatial filter
# ---------------------------------------------------------------------------

def _stage1_plot_ids(geojson, campaign_name, conn, schema: str):
    filters = {}
    if campaign_name:
        filters["campaign_name"] = campaign_name
    if geojson:
        filters["geom"] = geojson

    where_clause, where_params = build_where_clause("plot_shape_view", filters)
    sql = f'SELECT DISTINCT plot_id FROM "{schema}".plot_shape_view{where_clause}'
    logger.debug("Stage 1 SQL: %s", sql)

    df = pd.read_sql(sql, conn, params=list(where_params))
    return df["plot_id"].tolist()


def _plot_ids_with_traits(plot_ids, trait_filters, schema: str):
    where_clause, where_params = _trait_where(trait_filters, plot_ids)
    sql = f'SELECT DISTINCT plot_id FROM "{schema}".trait_view{where_clause}'
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=list(where_params))
    return df["plot_id"].tolist()


def _plot_ids_with_granules(plot_ids, granule_filters, schema: str):
    cte_sql, pixel_fragment, params = _granule_cte_and_where(granule_filters, plot_ids, schema)
    sql = f"""
        {cte_sql}
        SELECT DISTINCT px.plot_id
        FROM filtered_granules fg
        JOIN "{schema}".pixel px ON px.granule_id = fg.granule_id
        WHERE {pixel_fragment}
    """
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=params)
    return df["plot_id"].tolist()


# ---------------------------------------------------------------------------
# Stage 2 — parallel COUNT queries
# ---------------------------------------------------------------------------

def _count_traits(plot_ids, trait_filters, schema: str):
    where_clause, where_params = _trait_where(trait_filters, plot_ids)
    sql = f'SELECT COUNT(*) AS n FROM "{schema}".trait_view{where_clause}'
    logger.debug("Count traits SQL: %s", sql)
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=list(where_params))
    return int(df["n"].iloc[0])


def _count_granules_and_pixels(plot_ids, granule_filters, schema: str):
    """Return (total_granules, total_pixels) in a single query.

    total_pixels is COUNT(*) of the same granule/pixel join used elsewhere —
    i.e. the same number the frontend used to compute client-side by summing
    len(pixel_ids) across every granule in an unpaginated fetch-all response.
    Computing it here avoids ever transferring the raw pixel_id arrays for
    that purpose.
    """
    cte_sql, pixel_fragment, params = _granule_cte_and_where(granule_filters, plot_ids, schema)
    sql = f"""
        {cte_sql}
        SELECT COUNT(DISTINCT fg.granule_id) AS n_granules, COUNT(*) AS n_pixels
        FROM filtered_granules fg
        JOIN "{schema}".pixel px ON px.granule_id = fg.granule_id
        WHERE {pixel_fragment}
    """
    logger.debug("Count granules/pixels SQL: %s", sql)
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=params)
    return int(df["n_granules"].iloc[0]), int(df["n_pixels"].iloc[0])


def _trait_counts_by_plot(plot_ids, trait_filters, schema: str):
    """Return {plot_id: trait_row_count} for every plot with at least one matching trait row."""
    where_clause, where_params = _trait_where(trait_filters, plot_ids)
    sql = f'SELECT plot_id, COUNT(*) AS n FROM "{schema}".trait_view{where_clause} GROUP BY plot_id'
    logger.debug("Trait counts by plot SQL: %s", sql)
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=list(where_params))
    return dict(zip(df["plot_id"], df["n"]))


def _granule_counts_by_plot(plot_ids, granule_filters, schema: str):
    """Return {plot_id: distinct_granule_count} for every plot with at least one matching granule."""
    cte_sql, pixel_fragment, params = _granule_cte_and_where(granule_filters, plot_ids, schema)
    sql = f"""
        {cte_sql}
        SELECT px.plot_id, COUNT(DISTINCT fg.granule_id) AS n
        FROM filtered_granules fg
        JOIN "{schema}".pixel px ON px.granule_id = fg.granule_id
        WHERE {pixel_fragment}
        GROUP BY px.plot_id
    """
    logger.debug("Granule counts by plot SQL: %s", sql)
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=params)
    return dict(zip(df["plot_id"], df["n"]))


def _total_csv_rows(plot_ids, trait_filters, granule_filters, schema: str):
    """One row per trait measurement, joined against every overlapping granule
    (min 1 row per trait, matching the CSV export logic in the frontend) —
    computed as small per-plot aggregates instead of materializing full rows.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        tf = pool.submit(_trait_counts_by_plot,   plot_ids, trait_filters,   schema)
        gf = pool.submit(_granule_counts_by_plot, plot_ids, granule_filters, schema)
        trait_counts   = tf.result()
        granule_counts = gf.result()

    return sum(
        n_traits * max(1, granule_counts.get(plot_id, 0))
        for plot_id, n_traits in trait_counts.items()
    )


# ---------------------------------------------------------------------------
# Stage 4 — parallel data queries for the page
# ---------------------------------------------------------------------------

def _fetch_plots(plot_ids_page, fmt, schema: str):
    if not plot_ids_page:
        return {}

    clauses = []
    params  = []
    _build_array_in_clause("plot_id", plot_ids_page, clauses, params)
    where = " WHERE " + clauses[0]
    sql = f'SELECT * FROM "{schema}".plot_shape_view{where}'

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


def _fetch_traits(plot_ids_page, trait_filters, schema: str):
    if not plot_ids_page:
        return []

    where_clause, where_params = _trait_where(trait_filters, plot_ids_page)
    sql = f'SELECT * FROM "{schema}".trait_view{where_clause}'
    logger.debug("Fetch traits SQL: %s", sql)

    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=list(where_params))
    return df.to_dict(orient="records")


def _fetch_granules(plot_ids_page, granule_filters, schema: str):
    if not plot_ids_page:
        return []

    cte_sql, pixel_fragment, params = _granule_cte_and_where(granule_filters, plot_ids_page, schema)

    # pixel_plot_counts groups by (granule_id, plot_id) to get per-plot pixel counts.
    # plot_pixel_maps then collapses those into one row per granule as a JSON map —
    # this prevents a fan-out when joining back to the main pixel aggregation.
    # px_params are needed a second time for the pixel_plot_counts CTE.
    px_clauses = []
    px_params  = []
    _build_array_in_clause("plot_id", plot_ids_page, px_clauses, px_params)
    full_params = list(params) + px_params

    sql = f"""
        {cte_sql},
        pixel_plot_counts AS (
            SELECT px.granule_id, px.plot_id, count(*) AS pixel_count
            FROM "{schema}".pixel px
            WHERE {pixel_fragment}
            GROUP BY px.granule_id, px.plot_id
        ),
        plot_pixel_maps AS (
            SELECT granule_id,
                   json_object_agg(plot_id::text, pixel_count)::jsonb AS plot_pixel_map
            FROM pixel_plot_counts
            GROUP BY granule_id
        )
        SELECT
            fg.granule_id,
            fg.campaign_name,
            fg.sensor_name,
            fg.sensor_date,
            fg.acquisition_date,
            fg.acquisition_start_time,
            fg.cloudy_conditions,
            fg.cloud_type,
            array_agg(DISTINCT px.plot_id)              AS plot_ids,
            array_agg(px.pixel_id ORDER BY px.pixel_id) AS pixel_ids,
            ppm.plot_pixel_map
        FROM filtered_granules fg
        JOIN "{schema}".pixel px ON px.granule_id = fg.granule_id
        JOIN plot_pixel_maps ppm ON ppm.granule_id = fg.granule_id
        WHERE {pixel_fragment}
        GROUP BY
            fg.granule_id, fg.campaign_name, fg.sensor_name, fg.sensor_date,
            fg.acquisition_date, fg.acquisition_start_time,
            fg.cloudy_conditions, fg.cloud_type,
            ppm.plot_pixel_map
    """
    logger.debug("Fetch granules SQL: %s", sql)

    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=full_params)

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
# Citations — DOIs that apply to everything the query matched
# ---------------------------------------------------------------------------

def _fetch_citations(plot_ids, trait_filters, granule_filters, schema: str):
    """
    Return the doi rows whose role + scope match what is actually in the
    result set. Runs over ALL matching plot_ids (not just the page) so the
    citations cover everything the user can download.

    Each doi row is a rule; a NULL scope means the whole campaign:
      radiance_dataset / pixel_shade_mask → a granule of that sensor is in the results
      plot_information / plot_shapes      → a plot from one of its site_ids
      plot_method                         → a plot with that plot_method
      trait_method                        → that (trait, method)
      trait_data                          → that trait (and method, if set)
      anything else                       → the campaign has plots in the results
    """
    cte_sql, pixel_fragment, granule_params = _granule_cte_and_where(granule_filters, plot_ids, schema)

    plot_clauses, plot_params = [], []
    _build_array_in_clause("plot_id", plot_ids, plot_clauses, plot_params)

    trait_where, trait_params = _trait_where(trait_filters, plot_ids)
    trait_fragment = trait_where.lstrip().removeprefix("WHERE").strip()

    # Staged data can belong to a campaign that is already in production, and
    # a DOI already in production isn't staged again — look in both.
    doi_source = f'"{schema}".doi'
    if schema != "vswir_plants":
        doi_cols = ("campaign_name::text AS campaign_name, doi, citation_text, role, "
                    "sensor_name, plot_method, trait, trait_method, site_ids")
        doi_source = (f'(SELECT {doi_cols} FROM "{schema}".doi '
                      f'UNION ALL SELECT {doi_cols} FROM vswir_plants.doi)')

    sql = f"""
        {cte_sql},
        sensors_used AS (
            SELECT DISTINCT fg.campaign_name, fg.sensor_name
            FROM filtered_granules fg
            JOIN "{schema}".pixel px ON px.granule_id = fg.granule_id
            WHERE {pixel_fragment}
        ),
        plots_used AS (
            SELECT DISTINCT campaign_name, plot_method, site_id
            FROM "{schema}".plot_shape_view
            WHERE {plot_clauses[0]}
        ),
        traits_used AS (
            SELECT DISTINCT campaign_name, trait, method
            FROM "{schema}".trait_view
            WHERE {trait_fragment}
              AND trait IS NOT NULL  -- trait_view LEFT JOINs leaf_traits
        )
        SELECT DISTINCT d.campaign_name::text, d.doi, d.citation_text, d.role::text,
               d.sensor_name::text, d.plot_method::text, d.trait::text, d.trait_method::text,
               d.site_ids
        FROM {doi_source} d
        WHERE d.campaign_name::text IN (SELECT campaign_name::text FROM plots_used)
          AND CASE
            WHEN d.role IN ('radiance_dataset', 'pixel_shade_mask') THEN EXISTS (
                SELECT 1 FROM sensors_used s
                WHERE s.campaign_name::text = d.campaign_name::text
                  AND (d.sensor_name IS NULL OR s.sensor_name = d.sensor_name))
            WHEN d.role IN ('plot_information', 'plot_shapes') THEN EXISTS (
                SELECT 1 FROM plots_used p
                WHERE p.campaign_name::text = d.campaign_name::text
                  AND (d.site_ids IS NULL OR p.site_id = ANY(d.site_ids)))
            WHEN d.role = 'plot_method' THEN EXISTS (
                SELECT 1 FROM plots_used p
                WHERE p.campaign_name::text = d.campaign_name::text
                  AND (d.plot_method IS NULL OR p.plot_method = d.plot_method))
            WHEN d.role = 'trait_method' THEN EXISTS (
                SELECT 1 FROM traits_used t
                WHERE t.campaign_name::text = d.campaign_name::text
                  AND t.trait = d.trait AND t.method = d.trait_method)
            WHEN d.role = 'trait_data' THEN EXISTS (
                SELECT 1 FROM traits_used t
                WHERE t.campaign_name::text = d.campaign_name::text AND t.trait = d.trait
                  AND (d.trait_method IS NULL OR t.method = d.trait_method))
            ELSE TRUE
          END
        ORDER BY 1, 4, 2
    """
    # placeholder order: granule CTE, pixel fragment, plots_used, traits_used
    params = list(granule_params) + plot_params + list(trait_params)
    logger.debug("Citations SQL: %s", sql)

    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=params)

    return [
        {k: (None if not isinstance(v, list) and pd.isna(v) else v) for k, v in row.items()}
        for row in df.to_dict("records")
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_linked_query(body: dict, schema: str = "vswir_plants") -> dict:
    """
    Execute the 4-stage linked query and return the assembled response body.
    'schema' is the PostgreSQL schema name — either 'vswir_plants' (production)
    or 'vswir_plants_staging' (staging). Both are queried via the same
    postgrest_user DB connection.
    """
    campaign_name   = body.get("campaign_name")
    geojson         = body.get("geojson")
    trait_filters   = body.get("trait_filters") or {}
    granule_filters = body.get("granule_filters") or {}
    fmt             = (body.get("format") or "json").lower()
    limit           = int(body.get("limit", 100))
    offset          = int(body.get("offset", 0))

    # Stage 1 — spatial filter
    with get_connection() as conn:
        all_plot_ids = _stage1_plot_ids(geojson, campaign_name, conn, schema)

    if trait_filters and granule_filters:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            tf = pool.submit(_plot_ids_with_traits,   all_plot_ids, trait_filters,   schema)
            gf = pool.submit(_plot_ids_with_granules, all_plot_ids, granule_filters, schema)
            trait_plot_ids   = set(tf.result())
            granule_plot_ids = set(gf.result())
        all_plot_ids = [p for p in all_plot_ids if p in trait_plot_ids and p in granule_plot_ids]
    elif trait_filters:
        trait_plot_ids = set(_plot_ids_with_traits(all_plot_ids, trait_filters, schema))
        all_plot_ids = [p for p in all_plot_ids if p in trait_plot_ids]
    elif granule_filters:
        granule_plot_ids = set(_plot_ids_with_granules(all_plot_ids, granule_filters, schema))
        all_plot_ids = [p for p in all_plot_ids if p in granule_plot_ids]

    total_plots = len(all_plot_ids)

    if not all_plot_ids:
        return {
            "total_plots":       0,
            "total_traits":      0,
            "total_granules":    0,
            "total_pixel_count": 0,
            "total_csv_rows":    0,
            "truncated":         False,
            "plots":             [],
            "traits":            [],
            "granules":          [],
            "citations":         [],
        }

    # Stage 2 — parallel COUNT queries (traits, granules+pixels, csv row total).
    # None of these transfer raw rows/arrays — only small aggregate results.
    # Citations depend on the full result set, not the page, so they're only
    # computed on the first page and the frontend keeps them while paging.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        trait_count_future    = pool.submit(_count_traits, all_plot_ids, trait_filters, schema)
        granule_pixel_future  = pool.submit(_count_granules_and_pixels, all_plot_ids, granule_filters, schema)
        csv_rows_future       = pool.submit(_total_csv_rows, all_plot_ids, trait_filters, granule_filters, schema)
        citations_future      = (
            pool.submit(_fetch_citations, all_plot_ids, trait_filters, granule_filters, schema)
            if offset == 0 else None
        )
        total_traits   = trait_count_future.result()
        total_granules, total_pixel_count = granule_pixel_future.result()
        total_csv_rows = csv_rows_future.result()
        citations      = citations_future.result() if citations_future else None

    # Stage 3 — paginate
    truncated     = total_plots > (offset + limit)
    plot_ids_page = all_plot_ids[offset: offset + limit]

    # Stage 4 — parallel data queries for the page
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        plots_future    = pool.submit(_fetch_plots,    plot_ids_page, fmt,             schema)
        traits_future   = pool.submit(_fetch_traits,   plot_ids_page, trait_filters,   schema)
        granules_future = pool.submit(_fetch_granules, plot_ids_page, granule_filters, schema)
        plots_payload = plots_future.result()
        page_traits   = traits_future.result()
        page_granules = granules_future.result()

    logger.debug(
        "Linked query (%s): %d plots total (%d traits, %d granules, %d pixels, %d csv rows), page %d-%d",
        schema, total_plots, total_traits, total_granules, total_pixel_count, total_csv_rows, offset, offset + limit,
    )

    response = {
        "total_plots":       total_plots,
        "total_traits":      total_traits,
        "total_granules":    total_granules,
        "total_pixel_count": total_pixel_count,
        "total_csv_rows":    total_csv_rows,
        "truncated":         truncated,
        "traits":            page_traits,
        "granules":          page_granules,
    }
    if citations is not None:
        response["citations"] = citations
    response.update(plots_payload)
    return response
