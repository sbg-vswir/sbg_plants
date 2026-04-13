import os
import json
import logging
import boto3
from botocore.config import Config
from datetime import datetime, timezone
from functools import lru_cache

logger = logging.getLogger(__name__)

REGION = os.environ.get("AWS_REGION", "us-west-2")

# Force SigV4 for presigned URLs — required for us-west-2 and all non-us-east-1 regions
_sigv4 = Config(signature_version="s3v4")

s3       = boto3.client("s3",       region_name=REGION, config=_sigv4)
dynamodb = boto3.client("dynamodb", region_name=REGION)
lambda_  = boto3.client("lambda",   region_name=REGION)

BUCKET        = os.environ["CONFIG_BUCKET"]
JOB_TABLE     = os.environ["JOB_TABLE"]
QAQC_FUNCTION = os.environ["QAQC_FUNCTION_NAME"]

BUNDLE_CONFIG_KEY = "ingestion/bundle_config.json"


@lru_cache(maxsize=1)
def get_file_slots() -> dict:
    """
    Fetch the bundle file slot definitions from S3.
    Cached per warm Lambda instance — only one S3 call per container lifetime.
    Returns { slot_name: file_extension } e.g. { "spectra": ".csv" }
    """
    resp   = s3.get_object(Bucket=BUCKET, Key=BUNDLE_CONFIG_KEY)
    config = json.loads(resp["Body"].read())
    return config["file_slots"]


def get_upload_urls(batch_id: str) -> dict:
    """
    Generate presigned S3 PUT URLs for each file slot in a new batch.
    Returns { slot_name: presigned_url }
    """
    slots = get_file_slots()
    urls = {}
    for slot, ext in slots.items():
        key = f"ingestion/{batch_id}/raw/{slot}{ext}"
        urls[slot] = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=3600,
        )
        logger.info("Generated presigned PUT URL for slot '%s' batch_id=%s", slot, batch_id)
    return urls


def get_replace_url(batch_id: str, slot: str) -> str:
    """Generate a presigned S3 PUT URL for replacing a single file slot."""
    slots = get_file_slots()
    if slot not in slots:
        raise ValueError(f"Unknown file slot: {slot}")
    ext = slots[slot]
    key = f"ingestion/{batch_id}/raw/{slot}{ext}"
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=3600,
    )


def create_batch_record(batch_id: str, username: str, uploaded_at: str) -> None:
    """Write the initial PENDING record to DynamoDB."""
    dynamodb.put_item(
        TableName=JOB_TABLE,
        Item={
            "job_id":      {"S": batch_id},
            "job_type":    {"S": "ingestion_batch"},
            "status":      {"S": "PENDING"},
            "uploaded_by": {"S": username},
            "uploaded_at": {"S": uploaded_at},
            "created_at":  {"S": uploaded_at},
            "files":       {"SS": list(get_file_slots().keys())},
        },
    )
    logger.info("Created DynamoDB record batch_id=%s", batch_id)


def invoke_qaqc(batch_id: str) -> None:
    """Asynchronously invoke the QAQC Lambda — fire and forget."""
    lambda_.invoke(
        FunctionName=QAQC_FUNCTION,
        InvocationType="Event",
        Payload=json.dumps({"batch_id": batch_id}).encode(),
    )
    logger.info("Invoked QAQC Lambda for batch_id=%s", batch_id)


def list_batches() -> list:
    """Query DynamoDB for all ingestion_batch records, newest first."""
    resp = dynamodb.query(
        TableName=JOB_TABLE,
        IndexName="job_type-index",
        KeyConditionExpression="job_type = :t",
        ExpressionAttributeValues={":t": {"S": "ingestion_batch"}},
        ScanIndexForward=False,
        Limit=50,
    )
    return [_deserialize(item) for item in resp.get("Items", [])]


def get_batch(batch_id: str) -> dict | None:
    """Fetch a single batch record by batch_id. Returns None if not found."""
    resp = dynamodb.get_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": batch_id}},
    )
    item = resp.get("Item")
    return _deserialize(item) if item else None


def get_qaqc_report_presigned_url(s3_key: str) -> str:
    """Generate a 6-hour presigned URL for the QAQC report in S3."""
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": BUCKET, "Key": s3_key},
        ExpiresIn=6 * 3600,
    )


def reset_batch_for_recheck(batch_id: str) -> None:
    """Reset a QAQC_FAIL batch status back to PENDING so it can be re-checked."""
    dynamodb.update_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": batch_id}},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": {"S": "PENDING"}},
    )
    logger.info("Reset batch_id=%s to PENDING for recheck", batch_id)


def _deserialize(item: dict) -> dict:
    """Flatten DynamoDB typed attributes to plain Python values."""
    result = {}
    for k, v in item.items():
        if "S" in v:
            result[k] = v["S"]
        elif "N" in v:
            result[k] = float(v["N"])
        elif "BOOL" in v:
            result[k] = v["BOOL"]
        elif "SS" in v:
            result[k] = list(v["SS"])
        elif "M" in v:
            result[k] = _deserialize(v["M"])
        elif "NULL" in v:
            result[k] = None
    return result
