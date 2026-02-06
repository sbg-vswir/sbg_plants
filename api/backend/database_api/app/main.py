import json
import io
import base64
import logging

import geopandas as gpd
import shapely.wkt
import shapely.geometry

from app.query import ALLOWED_VIEWS, ASYNC_VIEWS, execute_query, build_query
from app.select_config import SELECTABLE_COLUMNS
from app.sqs import send_sqs


logger = logging.getLogger("lambda_handler")
logger.setLevel(logging.WARNING)

def lambda_handler(event, context):
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    debug = query_params.get("debug", "false").lower() == "true"
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    view_name = path_params.get("view_name")
    if not view_name:
        logger.debug("Missing view_name in request")
        return {"statusCode": 400, "body": json.dumps({"error": "Missing view_name"})}

    if view_name not in ALLOWED_VIEWS:
        logger.debug("View not allowed: %s", view_name)
        return {"statusCode": 400, "body": json.dumps({"error": "View not allowed"})}

    limit = query_params.get("limit")
    try:
        limit = int(limit) if limit else None
        logger.debug("Limit set to: %s", limit)
    except ValueError:
        logger.debug("Invalid limit: %s", limit)
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid limit"})}

    offset = query_params.get("offset")
    try:
        offset = int(offset) if offset else None
        logger.debug("Offset set to: %s", offset)
    except ValueError:
        logger.debug("Invalid offset: %s", offset)
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid offset"})}

    select = query_params.get("select")

    if select is None:
        select_statement = "*"
    else:
        try:
            select = json.loads(select)
        except json.JSONDecodeError:
            select = [select]  # wrap single column in list

        # Validate columns using set operation
        invalid_cols = set(select) - set(SELECTABLE_COLUMNS[view_name])
        if invalid_cols:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid columns: {', '.join(invalid_cols)}"})
            }
            
        select_statement = ", ".join(select)

    logger.debug("Selecting columns: %s", select_statement)
    
    filters_str = query_params.get("filters")
    try:
        filters = json.loads(filters_str) if filters_str else None
        logger.debug("Filters parsed: %s", filters)
    except json.JSONDecodeError:
        logger.debug("Invalid JSON for filters: %s", filters_str)
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON for filters"})}
    
    try:
        sql, params = build_query(view_name=view_name, select_statement=select_statement, limit=limit, offset=offset, filters=filters)
    except Exception as e:
        logger.exception("Database error")
        return {"statusCode": 500, "body": json.dumps({"error": f"Database error: {str(e)}"})}
    
    if ASYNC_VIEWS[view_name]:
        try:
            job_id = send_sqs(sql, params, debug)
        except Exception as e:
            logger.exception("sqs error")
            return {"statusCode": 500, "body": json.dumps({"error": f"Database error: {str(e)}"})}
        
        logger.debug(f"Submitted job: {job_id} to worker")
        return {
            "statusCode": 200,
            "body": json.dumps({"job_id": job_id}),
            "headers": {"Content-Type": "application/json"}
        }
    else: 
        try:
            df = execute_query(view_name=view_name, sql=sql, params=params, debug=debug)
            logger.debug("Query returned %d rows", len(df))
        except Exception as e:
            logger.exception("Database error")
            return {"statusCode": 500, "body": json.dumps({"error": f"Database error: {str(e)}"})}
        
    if df.empty:
        logger.debug("Query returned no data")
        return {"statusCode": 404, "body": json.dumps({"error": "No data found"})}

    format_type = query_params.get("format", "json").lower()
    logger.debug("Requested format: %s", format_type)
    has_geom = "geom" in df.columns
    logger.debug("Geometry column present: %s", has_geom)

    # --- Parquet / GeoParquet ---
    if format_type in ("parquet", "geoparquet") and has_geom:
        logger.debug("Converting DataFrame to GeoDataFrame for GeoParquet")
        df["geom"] = df["geom"].apply(lambda g: shapely.wkt.loads(g) if isinstance(g, str) else g)
        df = gpd.GeoDataFrame(df, geometry="geom", crs="EPSG:4326")
        logger.debug("GeoDataFrame ready with %d rows", len(df))

        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False, engine="pyarrow")
        parquet_bytes = buffer.getvalue()
        logger.debug("GeoParquet generated, size=%d bytes", len(parquet_bytes))

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f"attachment; filename={view_name}.parquet"
            },
            "body": base64.b64encode(parquet_bytes).decode('utf-8'),
            "isBase64Encoded": True
        }
    
        
    elif format_type == "parquet":
        logger.debug("Converting DataFrame to standard Parquet")
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False, compression='snappy')
        parquet_bytes = buffer.getvalue()
        logger.debug("Parquet generated, size=%d bytes", len(parquet_bytes))

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f"attachment; filename={view_name}.parquet"
            },
            "body": base64.b64encode(parquet_bytes).decode('utf-8'),
            "isBase64Encoded": True
        }

    # --- GeoJSON ---
    elif format_type in ("json", "geojson") and has_geom:
        logger.debug("Converting DataFrame to GeoJSON")
        features = []
        for idx, row in df.iterrows():
            geom = row["geom"]
            if isinstance(geom, str):
                geom = shapely.wkt.loads(geom)
            geojson_geom = shapely.geometry.mapping(geom) if geom else None
            properties = row.drop("geom").to_dict()
            features.append({
                "type": "Feature",
                "geometry": geojson_geom,
                "properties": properties
            })

        geojson_obj = {"type": "FeatureCollection", "features": features}
        logger.debug("GeoJSON ready with %d features", len(features))

        return {
            "statusCode": 200,
            "body": json.dumps(geojson_obj, default=str),
            "isBase64Encoded": False,
            "headers": {
                "Content-Type": "application/geo+json",
                "Content-Disposition": f"attachment; filename={view_name}.geojson"
                }
            }

    # --- Default JSON ---
    else:
        logger.debug("Returning default JSON with %d records", len(df))
        body = df.to_dict(orient="records")
        return {
            "statusCode": 200,
            "body": json.dumps(body),
            "headers": {"Content-Type": "application/json"}
        }













# import json
# import io
# import logging
# from app.query import ALLOWED_VIEWS, query_view
# import geopandas as gpd
# import shapely.wkt
# import shapely.geometry

# # --- Configure module-level logger ---
# logger = logging.getLogger("lambda_handler")
# logger.setLevel(logging.WARNING)
# handler = logging.StreamHandler()
# formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
# handler.setFormatter(formatter)
# logger.addHandler(handler)
# logger.propagate = False

# def handler(event, context):
#     path_params = event.get("pathParameters") or {}
#     query_params = event.get("queryStringParameters") or {}

#     debug = query_params.get("debug", "false").lower() == "true"
#     if debug:
#         logger.setLevel(logging.DEBUG)
#         logger.debug("Debug logging enabled")

#     view_name = path_params.get("view_name")
#     if not view_name:
#         logger.debug("Missing view_name in request")
#         return {"statusCode": 400, "body": json.dumps({"error": "Missing view_name"})}

#     if view_name not in ALLOWED_VIEWS:
#         logger.debug("View not allowed: %s", view_name)
#         return {"statusCode": 400, "body": json.dumps({"error": "View not allowed"})}

#     limit = query_params.get("limit")
#     try:
#         limit = int(limit) if limit else None
#         logger.debug("Limit set to: %s", limit)
#     except ValueError:
#         logger.debug("Invalid limit: %s", limit)
#         return {"statusCode": 400, "body": json.dumps({"error": "Invalid limit"})}

#     filters_str = query_params.get("filters")
#     try:
#         filters = json.loads(filters_str) if filters_str else None
#         logger.debug("Filters parsed: %s", filters)
#     except json.JSONDecodeError:
#         logger.debug("Invalid JSON for filters: %s", filters_str)
#         return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON for filters"})}

#     try:
#         df = query_view(view_name=view_name, limit=limit, filters=filters, debug=debug)
#         logger.debug("Query returned %d rows", len(df))
#     except Exception as e:
#         logger.exception("Database error")
#         return {"statusCode": 500, "body": json.dumps({"error": f"Database error: {str(e)}"})}

#     if df.empty:
#         logger.debug("Query returned no data")
#         return {"statusCode": 404, "body": json.dumps({"error": "No data found"})}

#     format_type = query_params.get("format", "json").lower()
#     logger.debug("Requested format: %s", format_type)
#     has_geom = "geom" in df.columns
#     logger.debug("Geometry column present: %s", has_geom)

#    # --- GeoParquet or Parquet with geometry ---
#     if format_type in ("geoparquet", "parquet") and has_geom:
#         logger.debug("Converting DataFrame to GeoDataFrame for GeoParquet")
#         gdf = df.copy()
#         gdf["geom"] = gdf["geom"].apply(lambda g: shapely.wkt.loads(g) if isinstance(g, str) else g)
#         gdf = gpd.GeoDataFrame(gdf, geometry="geom", crs="EPSG:4326")
#         buffer = io.BytesIO()
#         gdf.to_parquet(buffer, index=False, engine="pyarrow")
#         parquet_bytes = buffer.getvalue()
#         return {
#             "statusCode": 200,
#             "headers": {
#                 "Content-Type": "application/octet-stream",
#                 "Content-Disposition": f"attachment; filename={view_name}.parquet"
#             },
#             "body": parquet_bytes,
#             "isBase64Encoded": False
#         }

#     # --- Plain Parquet (no geometry) ---
#     elif format_type == "parquet":
#         logger.debug("Converting DataFrame to standard Parquet")
#         buffer = io.BytesIO()
#         df.to_parquet(buffer, index=False, compression='snappy')
#         parquet_bytes = buffer.getvalue()
#         return {
#             "statusCode": 200,
#             "headers": {
#                 "Content-Type": "application/octet-stream",
#                 "Content-Disposition": f"attachment; filename={view_name}.parquet"
#             },
#             "body": parquet_bytes,
#             "isBase64Encoded": False
#         }


#     # --- GeoJSON ---
#     elif format_type == "geojson" and has_geom:
#         logger.debug("Converting DataFrame to GeoJSON")
#         features = []
#         for idx, row in df.iterrows():
#             geom = row["geom"]
#             if isinstance(geom, str):
#                 geom = shapely.wkt.loads(geom)
#             geojson_geom = shapely.geometry.mapping(geom) if geom else None
#             properties = row.drop("geom").to_dict()
#             features.append({
#                 "type": "Feature",
#                 "geometry": geojson_geom,
#                 "properties": properties
#             })

#         geojson_obj = {"type": "FeatureCollection", "features": features}
#         logger.debug("GeoJSON ready with %d features", len(features))

#         return {
#             "statusCode": 200,
#             "body": json.dumps(geojson_obj),
#             "headers": {"Content-Type": "application/geo+json"},
#             "isBase64Encoded": False
#         }

#     # --- Default JSON ---
#     else:
#         logger.debug("Returning default JSON with %d records", len(df))
#         body = df.to_dict(orient="records")
#         return {
#             "statusCode": 200,
#             "body": json.dumps(body),
#             "headers": {"Content-Type": "application/json"},
#             "isBase64Encoded": False
#         }
