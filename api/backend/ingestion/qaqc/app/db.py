import os
import json
import boto3
from sqlalchemy import create_engine, text

REGION = os.environ.get("AWS_REGION", "us-west-2")
SECRET_ARN = os.environ["STAGING_DB_SECRET_ARN"]

_engine = None


def get_connection():
    global _engine
    if _engine is None:
        creds = _get_secret()
        url = (
            f"postgresql+psycopg2://{creds['username']}:{creds['password']}"
            f"@{creds['host']}:{creds.get('port', 5432)}/{creds['dbname']}"
        )
        _engine = create_engine(url, connect_args={"connect_timeout": 10})
    return _engine.connect()


def _get_secret() -> dict:
    client = boto3.client("secretsmanager", region_name=REGION)
    resp = client.get_secret_value(SecretId=SECRET_ARN)
    return json.loads(resp["SecretString"])


_enums_cache = None

def load_enums(conn=None) -> dict:
    """
    Load all enum values from the production DB into a dict.
    Returns { enum_name: set(values) }
    Cached per Lambda invocation.
    """
    global _enums_cache
    if _enums_cache is not None:
        return _enums_cache
    if conn is None:
        conn = get_connection()
    rows = conn.execute(text("""
        SELECT t.typname, e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON e.enumtypid = t.oid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'vswir_plants'
        ORDER BY t.typname, e.enumsortorder
    """)).fetchall()

    enums = {}
    for typname, label in rows:
        enums.setdefault(typname, set()).add(label)
    _enums_cache = enums
    return enums
