import json
import io
import base64
import logging
import math

import geopandas as gpd
import shapely.wkt
import shapely.geometry

from app.query import execute_query, build_query
from app.view_config import VIEW_CONFIG, get_selectable_columns
from app.sqs import send_sqs
from app.orchestration import run_linked_query


logger = logging.getLogger("lambda_handler")
logger.setLevel(logging.WARNING)


def _json_safe(obj):
    """json.dumps default= handler: NaN/Inf → None, dates → str."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return str(obj)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_body(event):
    """Parse the POST body as JSON; return empty dict on missing/invalid body."""
    try:
        return json.loads(event.get("body", "{}") or "{}")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON body")


def _format_response(df, view_name, format_type):
    """Serialise a DataFrame/GeoDataFrame to the requested format."""
    has_geom = "geom" in df.columns

    if format_type in ("parquet", "geoparquet") and has_geom:
        df["geom"] = df["geom"].apply(
            lambda g: shapely.wkt.loads(g) if isinstance(g, str) else g
        )
        df = gpd.GeoDataFrame(df, geometry="geom", crs="EPSG:4326")
        buf = io.BytesIO()
        df.to_parquet(buf, index=False, engine="pyarrow")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f"attachment; filename={view_name}.parquet",
            },
            "body": base64.b64encode(buf.getvalue()),
            "isBase64Encoded": True,
        }

    if format_type == "parquet":
        buf = io.BytesIO()
        df.to_parquet(buf, index=False, compression="snappy")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f"attachment; filename={view_name}.parquet",
            },
            "body": base64.b64encode(buf.getvalue()),
            "isBase64Encoded": True,
        }

    if format_type in ("json", "geojson") and has_geom:
        features = []
        for _, row in df.iterrows():
            geom = row["geom"]
            if isinstance(geom, str):
                geom = shapely.wkt.loads(geom)
            geojson_geom = shapely.geometry.mapping(geom) if geom else None
            properties = row.drop("geom").to_dict()
            features.append({"type": "Feature", "geometry": geojson_geom, "properties": properties})
        return {
            "statusCode": 200,
            "body": json.dumps({"type": "FeatureCollection", "features": features}, default=str),
            "isBase64Encoded": False,
            "headers": {
                "Content-Type": "application/geo+json",
                "Content-Disposition": f"attachment; filename={view_name}.geojson",
            },
        }

    # plain JSON
    return {
        "statusCode": 200,
        "body": json.dumps(df.to_dict(orient="records"), default=str),
        "headers": {"Content-Type": "application/json"},
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def handle_linked_query(event):
    """POST /query — 3-stage linked plot/trait/granule query."""
    try:
        body = _parse_body(event)
    except ValueError as exc:
        return {"statusCode": 400, "body": json.dumps({"error": str(exc)})}

    try:
        result = run_linked_query(body)
    except ValueError as exc:
        return {"statusCode": 400, "body": json.dumps({"error": str(exc)})}
    except Exception as exc:
        logger.exception("Linked query error")
        return {"statusCode": 500, "body": json.dumps({"error": f"Server error: {exc}"})}

    return {
        "statusCode": 200,
        "body": json.dumps(result, default=_json_safe),
        "headers": {"Content-Type": "application/json"},
    }


def handle_view_query(event, view_name):
    """POST /query/{view_name} and fixed sub-routes (spectra, reflectance, metadata)."""
    http_method = event.get("httpMethod", "GET").upper()

    if http_method == "POST":
        try:
            query_params = _parse_body(event)
        except ValueError as exc:
            return {"statusCode": 400, "body": json.dumps({"error": str(exc)})}
    else:
        query_params = event.get("queryStringParameters") or {}

    debug = query_params.get("debug", False)
    if isinstance(debug, str):
        debug = debug.strip().lower() in ("true", "1")
    else:
        debug = bool(debug)
    if debug:
        logger.setLevel(logging.DEBUG)

    if view_name not in VIEW_CONFIG:
        return {"statusCode": 400, "body": json.dumps({"error": "View not allowed"})}

    # limit / offset
    try:
        limit  = int(query_params["limit"])  if query_params.get("limit")  else None
        offset = int(query_params["offset"]) if query_params.get("offset") else None
    except ValueError:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid limit or offset"})}

    # select
    select = query_params.get("select")
    if select is None:
        select_statement = "*"
    else:
        if isinstance(select, str):
            try:
                select = json.loads(select)
            except json.JSONDecodeError:
                select = [select]
        elif not isinstance(select, list):
            select = [select]
        invalid = set(select) - set(get_selectable_columns(view_name))
        if invalid:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid columns: {', '.join(invalid)}"})}
        select_statement = ", ".join(select)

    # filters
    filters_param = query_params.get("filters")
    if isinstance(filters_param, str):
        try:
            filters = json.loads(filters_param)
        except json.JSONDecodeError:
            return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON for filters"})}
    elif isinstance(filters_param, dict):
        filters = filters_param
    elif filters_param is None:
        filters = None
    else:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid type for filters"})}

    try:
        sql, params = build_query(
            view_name=view_name,
            select_statement=select_statement,
            limit=limit,
            offset=offset,
            filters=filters,
        )
    except Exception as exc:
        logger.exception("Query build error")
        return {"statusCode": 500, "body": json.dumps({"error": f"Database error: {exc}"})}

    if VIEW_CONFIG[view_name]["is_async"]:
        try:
            spectral_metadata = query_params.get("metadata")
            job_id = send_sqs(sql, params, spectral_metadata, debug)
        except Exception as exc:
            logger.exception("SQS error")
            return {"statusCode": 500, "body": json.dumps({"error": f"SQS error: {exc}"})}
        return {
            "statusCode": 200,
            "body": json.dumps({"job_id": job_id}),
            "headers": {"Content-Type": "application/json"},
        }

    try:
        df = execute_query(view_name=view_name, sql=sql, params=params, debug=debug)
    except Exception as exc:
        logger.exception("Database error")
        return {"statusCode": 500, "body": json.dumps({"error": f"Database error: {exc}"})}

    if df.empty:
        return {"statusCode": 404, "body": json.dumps({"error": "No data found"})}

    format_type = query_params.get("format", "json").lower()
    return _format_response(df, view_name, format_type)


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    path        = (event.get("path") or event.get("rawPath") or "").rstrip("/")
    http_method = event.get("httpMethod", "GET").upper()

    logger.debug("Request: %s %s", http_method, path)

    # POST /query  (exact — must be checked before the prefix routes)
    if path == "/query" and http_method == "POST":
        return handle_linked_query(event)

    # Fixed sub-routes — checked before the /{view_name} wildcard
    if path == "/query/spectra":
        return handle_view_query(event, "extracted_spectra_view")

    if path == "/query/reflectance":
        return handle_view_query(event, "reflectance_view")

    if path == "/query/metadata":
        return handle_view_query(event, "extracted_metadata_view")

    # POST|GET /query/{view_name}
    if path.startswith("/query/"):
        view_name = path[len("/query/"):]
        return handle_view_query(event, view_name)

    logger.debug("No matching route for %s %s", http_method, path)
    return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}
