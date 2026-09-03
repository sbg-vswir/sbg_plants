import logging

from app.db import get_connection
from app.enum_config import SCHEMA_NAME, get_allowed_type_names

logger = logging.getLogger("lambda_handler")


def build_query():
    """
    Build the enum-catalog query. Every variable value — the schema name and
    the whitelist of allowed enum type names — is bound as a parameter, never
    formatted into the SQL text. The type-name whitelist is enforced here at
    the database level (t.typname = ANY(%s)), in addition to the Python-side
    whitelist in enum_config.get_frontend_key(), the same defense-in-depth
    pattern database_api/filter.py uses for column names.

    Returns:
        sql    (str)   : the query text, with %s placeholders only
        params (tuple) : parameters ready for psycopg2
    """
    sql = """
        SELECT t.typname, e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON e.enumtypid = t.oid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = %s
          AND t.typname = ANY(%s)
        ORDER BY t.typname, e.enumsortorder
    """
    params = (SCHEMA_NAME, get_allowed_type_names())

    logger.debug("Built enum query. Params: %s", params)

    return sql, params


def execute_query(sql: str, params: tuple):
    """Run the query and return the raw (typname, enumlabel) rows."""
    logger.debug("Executing enum query")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    logger.debug("Enum query returned %d rows", len(rows))
    return rows
