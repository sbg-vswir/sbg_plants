import logging
import pandas as pd
import geopandas as gpd
from app.db import get_connection
from app.filter import build_query


# --- Module-level logger setup ---
logger = logging.getLogger("query_view")
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = False  # avoid duplicate logging

ALLOWED_VIEWS = ["plot_pixels_mv", "insitu_sample_trait_mv"]

VIEW_MAP = {
    "plot_pixels_mv": True,
    "insitu_sample_trait_mv": True
}


def query_view(view_name: str, limit: int = None, offset: int = 0,  filters: dict = None, debug: bool = False):
    """
    Query a whitelisted view and return a pandas or geopandas DataFrame.
    Automatically returns GeoDataFrame if 'geom' column is present.
    Logging occurs only if debug=True.

    Parameters:
    - view_name: str, name of the whitelisted view
    - limit: int, optional max number of rows
    - filters: dict, optional column -> value mapping for filtering
    - debug: bool, enable debug logging

    Returns:
    - pd.DataFrame or gpd.GeoDataFrame
    """
    # --- Set logger level based on debug flag ---
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)

    if view_name not in ALLOWED_VIEWS:
        raise ValueError(f"View '{view_name}' is not allowed.")

    # --- Build SQL query ---
    sql = f'SELECT * FROM "{view_name}"'
    params = []

    # --- WHERE clause ---
    if filters:
        where_clause, where_params = build_query(view_name, filters, debug=False)
        sql += where_clause
        # Flatten tuple/list for GeoPandas / pandas
        if isinstance(where_params, (tuple, list)):
            params.extend(where_params)
        else:
            params.append(where_params)

    # --- LIMIT clause ---
    if limit:
        sql += " LIMIT %s"
        params.append(int(limit))
        
    # --- LIMIT clause ---
    if offset:
        sql += " OFFSET %s"
        params.append(int(offset))

    # --- Conditional debug logging ---
    logger.debug("Executing query on view: %s", view_name)
    logger.debug("SQL: %s", sql)
    logger.debug("Params: %s", params)
    logger.debug("Returning GeoDataFrame: %s", VIEW_MAP.get(view_name, False))

    # --- Execute query ---
    with get_connection() as conn:
        if VIEW_MAP.get(view_name, False):
            df = gpd.read_postgis(sql, conn, geom_col="geom", params=params)
        else:
            df = pd.read_sql(sql, conn, params=params)

    logger.debug("Query returned %d rows", len(df))
    return df
