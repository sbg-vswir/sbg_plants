import logging
import os
import json
import uuid
import boto3
import psycopg2
import psycopg2.extras
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGION         = os.environ.get("AWS_REGION", "us-west-2")
JOB_QUEUE      = os.environ["BATCH_JOB_QUEUE"]
JOB_DEFINITION = os.environ["BATCH_JOB_DEFINITION"]
JOB_TABLE      = os.environ["DYNAMODB_TABLE"]
BATCH_SIZE     = int(os.environ.get("BATCH_SIZE", "20"))

batch    = boto3.client("batch", region_name=REGION)
dynamodb = boto3.client("dynamodb", region_name=REGION)
secrets  = boto3.client("secretsmanager", region_name=REGION)


def chunk(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


@contextmanager
def get_connection():
    secret = json.loads(
        secrets.get_secret_value(SecretId=os.environ["DB_SECRET_ARN"])["SecretString"]
    )
    conn = psycopg2.connect(
        host=secret["host"],
        port="5432",
        dbname="vswirplants",
        user=secret["username"],
        password=secret["password"],
        connect_timeout=10,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_pixel_metadata(pixel_ranges: dict) -> dict:
    """
    Query pixels using BETWEEN clauses — one per [start, end] range pair.
    pixel_ranges: { "campaign|sensor": [[start, end], ...], ... }
    Returns: { (campaign_name, sensor_name, granule_id): [pixel_id, ...] }
    """
    # Collect all ranges across all sensor keys
    all_ranges = [r for ranges in pixel_ranges.values() for r in ranges]

    if not all_ranges:
        return {}

    # Build WHERE clause using BETWEEN for each range
    where_parts = " OR ".join("pixel_id BETWEEN %s AND %s" for _ in all_ranges)
    params = [val for r in all_ranges for val in r]

    sql = f"""
        SELECT pixel_id, campaign_name, sensor_name, granule_id
        FROM vswir_plants.extracted_spectra_view
        WHERE {where_parts}
    """

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    grouped = defaultdict(list)
    for row in rows:
        key = (row["campaign_name"], row["sensor_name"], row["granule_id"])
        grouped[key].append(row["pixel_id"])

    return dict(grouped)


def submit_job(
    parent_job_id: str,
    pixel_ids: list,
    batch_index: int,
    campaign_name: str,
    sensor_name: str,
    granule_id: str,
) -> str:
    job_id = str(uuid.uuid4())
    dynamodb.put_item(
        TableName=JOB_TABLE,
        Item={
            "job_id":        {"S": job_id},
            "parent_job_id": {"S": parent_job_id},
            "status":        {"S": "submitted"},
            "job_type":      {"S": "inversion"},
            "pixel_ids":     {"S": json.dumps(pixel_ids)},
            "pixel_count":   {"N": str(len(pixel_ids))},
            "batch_index":   {"N": str(batch_index)},
            "campaign_name": {"S": campaign_name},
            "sensor_name":   {"S": sensor_name},
            "granule_id":    {"S": granule_id},
            "created_at":    {"S": datetime.now(timezone.utc).isoformat()},
        }
    )
    try:
        response = batch.submit_job(
            jobName=f"inversion-{job_id[:8]}",
            jobQueue=JOB_QUEUE,
            jobDefinition=JOB_DEFINITION,
            containerOverrides={
                "environment": [
                    {"name": "PIXEL_IDS",      "value": ",".join(str(i) for i in pixel_ids)},
                    {"name": "CAMPAIGN_NAME",  "value": campaign_name},
                    {"name": "SENSOR_NAME",    "value": sensor_name},
                    {"name": "JOB_ID",         "value": job_id},
                ]
            }
        )
        # Store the Batch job ID so the status lambda can reconcile via batch.describe_jobs()
        dynamodb.update_item(
            TableName=JOB_TABLE,
            Key={"job_id": {"S": job_id}},
            UpdateExpression="SET batch_job_id = :b",
            ExpressionAttributeValues={":b": {"S": response["jobId"]}},
        )
    except Exception as e:
        logger.error(f"batch.submit_job failed for job {job_id}: {e}")
        dynamodb.update_item(
            TableName=JOB_TABLE,
            Key={"job_id": {"S": job_id}},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": {"S": "failed"}},
        )
        raise
    logger.info(
        f"submitted job {job_id} (batch {batch_index}) for {len(pixel_ids)} pixels "
        f"[{campaign_name}|{sensor_name}|{granule_id}]"
    )
    return job_id


def lambda_handler(event, context):
    from app.auth import get_claims, require_superadmin, handle_error

    try:
        claims = get_claims(event)
        require_superadmin(claims)
    except Exception as err:
        return handle_error(err)

    body = json.loads(event.get("body", "{}"))

    submitted_by = (
        event.get("requestContext", {})
             .get("authorizer", {})
             .get("jwt", {})
             .get("claims", {})
             .get("cognito:username", "unknown")
    )

    pixel_ranges = body.get("pixel_ranges")
    if not pixel_ranges or not isinstance(pixel_ranges, dict):
        return {"statusCode": 400, "body": json.dumps({"error": "missing or invalid pixel_ranges — expected { 'campaign|sensor': [[start, end], ...] }"})}

    logger.info(
        f"request from {submitted_by} — {len(pixel_ranges)} sensor key(s), "
        f"{sum(len(v) for v in pixel_ranges.values())} range(s)"
    )

    # Validate format — each key must be "campaign|sensor", each value a list of [start, end] pairs
    for sensor_key, ranges in pixel_ranges.items():
        if "|" not in sensor_key:
            return {"statusCode": 400, "body": json.dumps({"error": f"invalid key '{sensor_key}', expected 'campaign|sensor' format"})}
        if not isinstance(ranges, list):
            return {"statusCode": 400, "body": json.dumps({"error": f"ranges for '{sensor_key}' must be a list"})}
        for entry in ranges:
            if not (isinstance(entry, list) and len(entry) == 2 and all(isinstance(v, int) for v in entry)):
                return {"statusCode": 400, "body": json.dumps({"error": f"each range for '{sensor_key}' must be a [start, end] integer pair"})}

    # Query DB — group by (campaign, sensor, granule) using BETWEEN clauses
    try:
        grouped = fetch_pixel_metadata(pixel_ranges)
    except Exception as e:
        logger.error(f"DB query failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "database error", "detail": str(e)})}

    if not grouped:
        return {"statusCode": 400, "body": json.dumps({"error": "no pixels found for the provided ranges"})}

    logger.info(
        f"DB query returned {sum(len(v) for v in grouped.values())} pixels "
        f"across {len(grouped)} granule group(s)"
    )

    parent_job_id = str(uuid.uuid4())
    created_at    = datetime.now(timezone.utc).isoformat()
    job_ids       = []

    # Write the parent job record first so it exists before any child jobs
    dynamodb.put_item(
        TableName=JOB_TABLE,
        Item={
            "job_id":        {"S": parent_job_id},
            "job_type":      {"S": "isofit_parent"},
            "status":        {"S": "submitted"},
            "submitted_by":  {"S": submitted_by},
            "created_at":    {"S": created_at},
        }
    )

    # One job per (campaign, sensor, granule) group, capped at BATCH_SIZE pixels
    batch_index = 0
    for (campaign_name, sensor_name, granule_id), ids in grouped.items():
        for chunk_ids in chunk(ids, BATCH_SIZE):
            job_id = submit_job(
                parent_job_id=parent_job_id,
                pixel_ids=chunk_ids,
                batch_index=batch_index,
                campaign_name=campaign_name,
                sensor_name=sensor_name,
                granule_id=granule_id,
            )
            job_ids.append(job_id)
            batch_index += 1

    logger.info(f"submitted {len(job_ids)} jobs for parent_job_id={parent_job_id}")
    return {
        "statusCode": 202,
        "body": json.dumps({
            "parent_job_id":  parent_job_id,
            "job_count":      len(job_ids),
            "granule_count":  len(grouped),
            "submitted_by":   submitted_by,
            "created_at":     created_at,
        })
    }
