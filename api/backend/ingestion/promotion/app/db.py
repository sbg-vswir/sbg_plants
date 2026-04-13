import os
import json
import boto3
import psycopg2

REGION           = os.environ.get("AWS_REGION", "us-west-2")
PROMOTION_SECRET = os.environ["PROMOTION_DB_SECRET_ARN"]

_conn = None


def get_connection():
    global _conn
    if _conn is None or _conn.closed:
        secrets = boto3.client("secretsmanager", region_name=REGION)
        creds   = json.loads(
            secrets.get_secret_value(SecretId=PROMOTION_SECRET)["SecretString"]
        )
        _conn = psycopg2.connect(
            host=creds["host"],
            port=creds.get("port", 5432),
            dbname=creds["dbname"],
            user=creds["username"],
            password=creds["password"],
            connect_timeout=10,
        )
        _conn.autocommit = False
    return _conn
