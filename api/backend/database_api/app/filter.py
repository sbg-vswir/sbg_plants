import logging

from app.view_config import VIEW_CONFIG, get_filterable_columns, get_date_column
from app.filter_utils import (
    _get_field_type,
    _build_string_clause,
    _build_numeric_clause,
    _build_boolean_clause,
    _build_date_clause,
    _build_date_range_clauses,
    _build_geom_clause,
    _build_array_in_clause,
)

logger = logging.getLogger("lambda_handler")

# Fields that are handled specially and skipped in the main column loop
_SPECIAL_FIELDS = {"geom", "start_date", "end_date"}


def build_where_clause(view_name, filters):
    """
    Build a SQL WHERE clause and parameters for any view using validated filters.

    Parameters:
    - view_name : str, must be a key in VIEW_CONFIG
    - filters   : dict, column -> value mapping

    Returns:
        sql_where (str)  : the WHERE clause (including "WHERE"), or "" if no filters
        params    (tuple): parameters ready for psycopg2 / SQLAlchemy / GeoPandas
    """
    if view_name not in VIEW_CONFIG:
        raise ValueError(f"Unknown view: {view_name}. Available views: {list(VIEW_CONFIG.keys())}")

    allowed_fields = get_filterable_columns(view_name)
    date_column    = get_date_column(view_name)
    geom           = filters.get("geom")

    clauses = []
    params  = []

    for col, val in filters.items():
        if val is None:
            continue

        if col in _SPECIAL_FIELDS:
            continue

        if col not in allowed_fields:
            raise ValueError(f"Filtering by column '{col}' is not allowed for view '{view_name}'.")

        field_type = _get_field_type(view_name, col)

        if field_type == "string":
            _build_string_clause(col, val, clauses, params)
        elif field_type == "numeric":
            _build_numeric_clause(col, val, clauses, params)
        elif field_type == "boolean":
            _build_boolean_clause(col, val, clauses, params)
        elif field_type == "date":
            _build_date_clause(col, val, clauses, params)
        elif field_type == "array":
            _build_array_in_clause(col, val, clauses, params)
        else:
            raise ValueError(f"Unknown field type '{field_type}' for column '{col}' in view '{view_name}'")

    if date_column:
        _build_date_range_clauses(filters, date_column, clauses, params)

    if geom:
        _build_geom_clause(geom, clauses, params)

    sql_where = " WHERE " + " AND ".join(clauses) if clauses else ""

    logger.debug("Generated SQL WHERE clause: %s", sql_where)
    logger.debug("Generated params: %s", params)

    return sql_where, tuple(params)
