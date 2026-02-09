import logging

from app.filter_config import (
    SPECIAL_FIELDS,
    VIEW_FIELD_CONFIG
)

from app.filter_utils import (
    _get_field_type,
    _build_string_clause, 
    _build_numeric_clause, 
    _build_boolean_clause, 
    _build_date_clause, 
    _build_date_range_clauses, 
    _build_geom_clause
)


logger = logging.getLogger("lambda_handler")

def build_where_clause(view_name, filters):
    """
    Build a SQL WHERE clause and parameters for any view using validated filters.
    
    Parameters:
    - view_name: str, name of the view (must be in VIEW_FIELD_CONFIG)
    - filters: dict, column -> value mapping
    
    Returns:
        sql_where (str): the WHERE clause (including "WHERE"), or empty string if no filters
        params (tuple): tuple of parameters ready for psycopg2 / SQLAlchemy / GeoPandas
    """
    
    # Get view configuration
    if view_name not in VIEW_FIELD_CONFIG:
        raise ValueError(f"Unknown view: {view_name}. Available views: {list(VIEW_FIELD_CONFIG.keys())}")
    
    view_config = VIEW_FIELD_CONFIG[view_name]
    allowed_fields = view_config["allowed_fields"]
    date_column = view_config.get("date_column", None)
    geom = filters.get("geom", None)
    
    clauses = []
    params = []
     
    # Build clauses for each filter
    for col, val in filters.items():
        # Skip None values
        if val is None:
            continue
        
        # Skip special fields (handled separately below)
        if col in SPECIAL_FIELDS:
            continue
        
        # Validate column is allowed for this view
        if col not in allowed_fields:
            raise ValueError(f"Filtering by column '{col}' is not allowed for view '{view_name}'.")
        
        # Determine field type and build appropriate clause
        field_type = _get_field_type(col)
        
        if field_type == "string":
            _build_string_clause(col, val, clauses, params)
        elif field_type == "numeric":
            _build_numeric_clause(col, val, clauses, params)
        elif field_type == "boolean":
            _build_boolean_clause(col, val, clauses, params)
        elif field_type == "date":
            _build_date_clause(col, val, clauses, params)
        else:
            raise ValueError(f"Unknown field type for column '{col}'")
    
    if date_column:
        _build_date_range_clauses(filters, date_column, clauses, params)
    
    if geom:
        _build_geom_clause(geom, clauses, params)
    
    # Construct final WHERE clause
    sql_where = " WHERE " + " AND ".join(clauses) if clauses else ""
   
    logger.debug("Generated SQL WHERE clause: %s", sql_where)
    logger.debug("Generated params: %s", params)
    
    return sql_where, tuple(params)