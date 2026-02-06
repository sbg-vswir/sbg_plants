import json
import logging
from app.filter_config import (
    STRING_FIELDS,
    NUMERIC_FIELDS,
    BOOLEAN_FIELDS,
    DATE_FIELDS,
    SPECIAL_FIELDS,
    VIEW_FIELD_CONFIG
)

from app.filter_utils import (
    _get_field_type, _validate_polygon, 
    _build_string_clause, 
    _build_numeric_clause, 
    _build_boolean_clause, 
    _build_date_clause, 
    _build_date_range_clauses, 
    _build_polygon_clause
)

import logging

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
    date_column = view_config["date_column"]
    
    clauses = []
    params = []
    
    # Validate and extract polygon
    polygon = _validate_polygon(filters.get("polygon"))
    
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
    
    # Handle date range filters
    _build_date_range_clauses(filters, date_column, clauses, params)
    
    # Handle polygon filter
    _build_polygon_clause(polygon, clauses, params)
    
    # Construct final WHERE clause
    sql_where = " WHERE " + " AND ".join(clauses) if clauses else ""
   
    logger.debug("Generated SQL WHERE clause: %s", sql_where)
    logger.debug("Generated params: %s", params)
    
    return sql_where, tuple(params)

# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Example 1: plot_pixels_mv
    filters1 = {
        "plot_name": ["276-ER18", "001-ER18"],
        "campaign_name": ["East River 2018"],
        "start_date": "2018-01-01",
        "end_date": "2018-12-31"
    }
    sql, params = build_where_clause("plot_pixels_mv", filters1)
    print(f"\nSQL: {sql}")
    print(f"Params: {params}")
    
    # Example 2: insitu_sample_trait_mv with range
    filters2 = {
        "plot_name": ["276-ER18"],
        "trait": ["leaf_area"],
        "value": {"min": 0.5, "max": 1.5},
        "taxa": ["Salix planifolia"],
        "start_date": "2018-06-01"
    }
    sql, params = build_where_clause("insitu_sample_trait_mv", filters2)
    print(f"\nSQL: {sql}")
    print(f"Params: {params}")