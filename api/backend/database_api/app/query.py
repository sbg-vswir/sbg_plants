import logging
import pandas as pd
import geopandas as gpd
from app.db import get_connection
from app.filter import build_where_clause

logger = logging.getLogger("lambda_handler")

ALLOWED_VIEWS = ["plot_pixels_mv", "insitu_sample_trait_mv", "pixel_spectra_mv"]

VIEW_MAP = {
    "plot_pixels_mv": True,
    "insitu_sample_trait_mv": True,
    "pixel_spectra_mv": False
}

ASYNC_VIEWS = {
    "plot_pixels_mv": False,
    "insitu_sample_trait_mv": False,
    "pixel_spectra_mv": True
}


def build_query(view_name: str, select_statement:str,  limit: int = None, offset: int = 0,  filters: dict = None):
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

    if view_name not in ALLOWED_VIEWS:
        raise ValueError(f"View '{view_name}' is not allowed.")

    # --- Build SQL query ---
    sql = f'SELECT {select_statement} FROM "{view_name}"'
    params = []

    # --- WHERE clause ---
    if filters:
        where_clause, where_params = build_where_clause(view_name, filters)
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
    
    logger.debug("Built query for view: %s", view_name)
    logger.debug("SQL: %s", sql)
    logger.debug("Params: %s", params)
    
    return sql, params

def execute_query(view_name: str, sql: str, params: list, debug: bool = False):
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
