import json
import logging

from app.query import build_query, execute_query
from app.enum_config import get_frontend_key

logger = logging.getLogger("lambda_handler")
logger.setLevel(logging.WARNING)


_ENUMS_CACHE = None


def _load_enums():
    """
    Query Postgres's enum catalog (via query.py) and group the results into
    { frontend_key: [values...] }. Cached per warm Lambda container — enum
    values change rarely, so there's no need to hit the DB on every request.
    """
    global _ENUMS_CACHE
    if _ENUMS_CACHE is not None:
        return _ENUMS_CACHE

    sql, params = build_query()
    rows = execute_query(sql, params)

    enums = {}
    for typname, label in rows:
        key = get_frontend_key(typname)
        if key is None:
            continue  # not whitelisted for the frontend — defensive, build_query already filters this
        enums.setdefault(key, []).append(label)

    _ENUMS_CACHE = enums
    return enums


def _respond(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def lambda_handler(event, context):
    path        = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    http_method = event.get("httpMethod", "GET").upper()

    logger.debug("Request: %s %s", http_method, path)

    if path == "/enums" and http_method == "GET":
        try:
            enums = _load_enums()
        except Exception as exc:
            logger.exception("Error loading enums")
            return _respond(500, {"error": f"Server error: {exc}"})
        return _respond(200, enums)

    return _respond(404, {"error": "Not found"})
