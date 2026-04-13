import os
import json
import logging
import boto3
import psycopg2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dynamodb = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-west-2"))

JOB_TABLE       = os.environ["JOB_TABLE"]
STAGING_SECRET  = os.environ["STAGING_DB_SECRET_ARN"]
REGION          = os.environ.get("AWS_REGION", "us-west-2")

CORS_HEADERS = {
    "Content-Type":                 "application/json",
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Authorization,Content-Type",
}

# Reverse dependency order for safe deletion
STAGING_TABLES = [
    "extracted_spectra", "pixel", "leaf_traits", "sample",
    "insitu_plot_event", "plot_raster_intersect", "plot",
    "plot_shape", "granule", "sensor_campaign", "campaign",
]


def respond(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers":    CORS_HEADERS,
        "body":       json.dumps(body),
    }


def get_claims(event: dict) -> dict:
    return (
        event.get("requestContext", {})
             .get("authorizer", {})
             .get("jwt", {})
             .get("claims", {})
    )


def require_superadmin(claims: dict):
    groups = claims.get("cognito:groups", "")
    if isinstance(groups, str):
        groups = groups.split(",")
    if "superadmins" not in groups:
        raise PermissionError("superadmins group required")


def lambda_handler(event, context):
    try:
        claims = get_claims(event)
        require_superadmin(claims)
    except PermissionError as e:
        return respond(403, {"message": str(e)})
    except Exception:
        return respond(401, {"message": "Unauthorized"})

    batch_id = (event.get("pathParameters") or {}).get("batch_id")
    if not batch_id:
        return respond(400, {"message": "Missing batch_id"})

    # Verify batch exists and is not already PROMOTED
    item = dynamodb.get_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": batch_id}},
    ).get("Item")

    if not item:
        return respond(404, {"message": "Batch not found"})

    status = item.get("status", {}).get("S")
    if status == "PROMOTED":
        return respond(409, {"message": "Cannot reject a batch that has already been promoted"})

    logger.info("Rejecting batch_id=%s (current status=%s)", batch_id, status)

    try:
        conn = _get_connection()
        _delete_staging(conn, batch_id)
    except Exception as e:
        logger.exception("Rejection failed for batch_id=%s", batch_id)
        return respond(500, {"message": f"Rejection failed: {e}"})

    dynamodb.update_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": batch_id}},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": {"S": "REJECTED"}},
    )
    logger.info("Rejection complete for batch_id=%s", batch_id)
    return respond(200, {"batch_id": batch_id, "status": "REJECTED"})


def _delete_staging(conn, batch_id: str):
    with conn:
        with conn.cursor() as cur:
            for table in STAGING_TABLES:
                cur.execute(
                    f"DELETE FROM vswir_plants_staging.{table} WHERE batch_id = %s",
                    (batch_id,)
                )
                logger.info("Deleted staging %s rows for batch_id=%s", table, batch_id)


def _get_connection():
    secrets = boto3.client("secretsmanager", region_name=REGION)
    creds   = json.loads(secrets.get_secret_value(SecretId=STAGING_SECRET)["SecretString"])
    return psycopg2.connect(
        host=creds["host"],
        port=creds.get("port", 5432),
        dbname=creds["dbname"],
        user=creds["username"],
        password=creds["password"],
        connect_timeout=10,
    )
