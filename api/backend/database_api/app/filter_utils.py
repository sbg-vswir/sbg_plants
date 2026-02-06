import json

from app.filter_config import (
    STRING_FIELDS,
    NUMERIC_FIELDS,
    BOOLEAN_FIELDS,
    DATE_FIELDS,
    SPECIAL_FIELDS,
    VIEW_FIELD_CONFIG
)

# ============================================================================
#  QUERY BUILDING FUNCTIONS
# ============================================================================

def _validate_polygon(polygon):
    """Validate that polygon is a proper GeoJSON Polygon or MultiPolygon."""
    if polygon is None:
        return None
    
    if not (
        isinstance(polygon, dict)
        and polygon.get("type") in {"Polygon", "MultiPolygon"}
        and "coordinates" in polygon
    ):
        raise ValueError("`polygon` must be a GeoJSON Polygon or MultiPolygon")
    
    return polygon


def _build_string_clause(col, val, clauses, params):
    """Build WHERE clause for string fields (supports lists)."""
    if isinstance(val, list):
        if not val:
            return  # skip empty lists
        # Filter out None values from list
        val = [v for v in val if v is not None]
        if not val:
            return
        placeholders = ", ".join(["%s"] * len(val))
        clauses.append(f'"{col}" IN ({placeholders})')
        params.extend(val)
    else:
        clauses.append(f'"{col}" = %s')
        params.append(val)


def _build_numeric_clause(col, val, clauses, params):
    """Build WHERE clause for numeric fields (supports single value, list, or range)."""
    if isinstance(val, dict):
        # Support range queries: {"min": 0.5, "max": 1.5}
        if "min" in val and val["min"] is not None:
            clauses.append(f'"{col}" >= %s')
            params.append(val["min"])
        if "max" in val and val["max"] is not None:
            clauses.append(f'"{col}" <= %s')
            params.append(val["max"])
    elif isinstance(val, list):
        # Support list of specific values
        if not val:
            return
        val = [v for v in val if v is not None]
        if not val:
            return
        placeholders = ", ".join(["%s"] * len(val))
        clauses.append(f'"{col}" IN ({placeholders})')
        params.extend(val)
    else:
        # Single value
        clauses.append(f'"{col}" = %s')
        params.append(val)


def _build_boolean_clause(col, val, clauses, params):
    """Build WHERE clause for boolean fields."""
    if isinstance(val, bool):
        clauses.append(f'"{col}" = %s')
        params.append(val)
    elif isinstance(val, str):
        # Handle string representations of boolean
        bool_val = val.lower() in ("true", "t", "yes", "y", "1")
        clauses.append(f'"{col}" = %s')
        params.append(bool_val)
    else:
        raise ValueError(f"Invalid boolean value for '{col}': {val}")


def _build_date_clause(col, val, clauses, params):
    """Build WHERE clause for date fields."""
    if isinstance(val, list):
        if not val:
            return
        val = [v for v in val if v is not None]
        if not val:
            return
        placeholders = ", ".join(["%s"] * len(val))
        clauses.append(f'"{col}" IN ({placeholders})')
        params.extend(val)
    else:
        clauses.append(f'"{col}" = %s')
        params.append(val)


def _build_date_range_clauses(filters, date_column, clauses, params):
    """Build WHERE clauses for start_date and end_date filters."""
    if "start_date" in filters and filters["start_date"] is not None:
        clauses.append(f'"{date_column}" >= %s')
        params.append(filters["start_date"])
    
    if "end_date" in filters and filters["end_date"] is not None:
        clauses.append(f'"{date_column}" <= %s')
        params.append(filters["end_date"])


def _build_polygon_clause(polygon, clauses, params):
    """Build WHERE clause for polygon intersection."""
    if polygon is not None:
        clauses.append(
            'ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))'
        )
        params.append(json.dumps(polygon))


def _get_field_type(col):
    """Determine the type of a field."""
    if col in STRING_FIELDS:
        return "string"
    elif col in NUMERIC_FIELDS:
        return "numeric"
    elif col in BOOLEAN_FIELDS:
        return "boolean"
    elif col in DATE_FIELDS:
        return "date"
    elif col in SPECIAL_FIELDS:
        return "special"
    else:
        return None
