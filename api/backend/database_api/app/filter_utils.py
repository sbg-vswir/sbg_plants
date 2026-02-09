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
    """
    Build WHERE clause for numeric fields.
    
    Supports:
    - Single value: 5
    - List of values: [1,2,3]
    - Range dict: {"min": 0.5, "max": 1.5}
    - List of tuples (start, end) for ranges: [(1,3), (5,6)]
    """
    if isinstance(val, dict):
        # Range query: {"min": x, "max": y}
        if "min" in val and val["min"] is not None:
            clauses.append(f'"{col}" >= %s')
            params.append(val["min"])
        if "max" in val and val["max"] is not None:
            clauses.append(f'"{col}" <= %s')
            params.append(val["max"])
    
    elif isinstance(val, list):
        if not val:
            return

        # Check if it's a list of tuples (ranges)
        if all(isinstance(v, tuple) and len(v) == 2 or isinstance(v, list) and len(v) == 2 for v in val):
            # Each tuple is a range (start, end)
            range_clauses = []
            for start, end in val:
                if start == end:
                    range_clauses.append(f'"{col}" = %s')
                    params.append(start)
                else:
                    range_clauses.append(f'"{col}" BETWEEN %s AND %s')
                    params.extend([start, end])
            clauses.append("(" + " OR ".join(range_clauses) + ")")
        
        else:
            # Regular list of values
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


# def _build_geom_clause(geom, clauses, params):
#     """Build WHERE clause for geom intersection."""
#     # clauses.append(
#     #     'ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))'
#     # )
#     clauses.append(
#         'geom && ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) AND ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))'
#     )
#     params.append(json.dumps(geom))

def _build_geom_clause(geom, clauses, params):
    """Build WHERE clause for geom intersection."""
    # optimally uses the spatial index by first doing geom && ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) filtering via bounding boxes
    # the second query ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))" then parses out false positives, things withing the bbox but not the polygon
    clauses.append(
        "geom && ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) "
        "AND ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))"
    )
    params.extend([json.dumps(geom), json.dumps(geom)])



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
