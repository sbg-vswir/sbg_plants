import logging
import pandas as pd
import geopandas as gpd
from app.db import get_connection
from app.filter import build_where_clause
from app.view_config import VIEW_CONFIG

logger = logging.getLogger("lambda_handler")


def build_query(view_name: str, select_statement: str, limit: int = None, offset: int = 0, filters: dict = None):
    if view_name not in VIEW_CONFIG:
        raise ValueError(f"View '{view_name}' is not allowed.")

    sql = f'SELECT {select_statement} FROM "{view_name}"'
    params = []

    if filters:
        where_clause, where_params = build_where_clause(view_name, filters)
        sql += where_clause
        if isinstance(where_params, (tuple, list)):
            params.extend(where_params)
        else:
            params.append(where_params)

    if limit:
        sql += " LIMIT %s"
        params.append(int(limit))

    if offset:
        sql += " OFFSET %s"
        params.append(int(offset))

    logger.debug("Built query for view: %s", view_name)
    logger.debug("SQL: %s", sql)
    logger.debug("Params: %s", params)

    return sql, params


def execute_query(view_name: str, sql: str, params: list, debug: bool = False):
    logger.debug("Executing query on view: %s", view_name)
    logger.debug("SQL: %s", sql)
    logger.debug("Params: %s", params)

    has_geo = VIEW_CONFIG[view_name]["has_geo"]
    logger.debug("Returning GeoDataFrame: %s", has_geo)

    with get_connection() as conn:
        if has_geo:
            try:
                df = gpd.read_postgis(sql, conn, geom_col="geom", params=params)
            except ValueError:
                # geopandas raises ValueError on empty result sets with no geometry
                # to infer the CRS from — fall back to a plain DataFrame
                df = pd.read_sql(sql, conn, params=params)
        else:
            df = pd.read_sql(sql, conn, params=params)

    logger.debug("Query returned %d rows", len(df))
    return df
