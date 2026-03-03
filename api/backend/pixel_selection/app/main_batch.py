import logging
import os
import json
import uuid
import boto3
from datetime import datetime, timezone
from app.db import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGION         = os.environ.get("AWS_REGION", "us-west-2")
JOB_QUEUE      = os.environ["BATCH_JOB_QUEUE"]
JOB_DEFINITION = os.environ["BATCH_JOB_DEFINITION"]
JOB_TABLE      = os.environ["DYNAMODB_TABLE"]
BATCH_SIZE     = int(os.environ.get("BATCH_SIZE", "20"))

batch    = boto3.client("batch", region_name=REGION)
dynamodb = boto3.client("dynamodb", region_name=REGION)


def chunk(lst: list, size: int):
    # split a list into chunks of at most `size` elements
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def submit_job(parent_job_id: str, pixel_ids: list, batch_index: int, campaign_name: str, sensor_name: str) -> str:
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
            "created_at":    {"S": datetime.now(timezone.utc).isoformat()},
        }
    )
    batch.submit_job(
        jobName=f"inversion-{job_id[:8]}",
        jobQueue=JOB_QUEUE,
        jobDefinition=JOB_DEFINITION,
        containerOverrides={
            "environment": [
                {"name": "PIXEL_IDS",      "value": ",".join(str(i) for i in pixel_ids)},
                {"name": "CAMPAIGN_NAME",  "value": campaign_name},
                {"name": "SENSOR_NAME",    "value": sensor_name},
            ]
        }
    )
    logger.info(f"submitted job {job_id} (batch {batch_index}) for {len(pixel_ids)} pixels [{campaign_name}|{sensor_name}]")
    return job_id


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))
    pixel_ranges = body.get("pixel_ranges")
    
    if not pixel_ranges:
        return {"statusCode": 400, "body": json.dumps({"error": "missing pixel_ranges"})}

    parent_job_id = str(uuid.uuid4())
    job_ids = []

    for sensor_key, ranges in pixel_ranges.items():
        campaign_name, sensor_name = sensor_key.split("|")

        # Expand ranges to flat pixel id list
        pixel_ids = []
        for start, end in ranges:
            pixel_ids.extend(range(start, end + 1))

        if not pixel_ids:
            continue

        for i, chunk_ids in enumerate(chunk(pixel_ids, BATCH_SIZE)):
            job_id = submit_job(
                parent_job_id=parent_job_id,
                pixel_ids=chunk_ids,
                batch_index=i,
                campaign_name=campaign_name,
                sensor_name=sensor_name
            )
            job_ids.append(job_id)

    if not job_ids:
        return {"statusCode": 400, "body": json.dumps({"error": "no pixels found in ranges"})}

    logger.info(f"submitted {len(job_ids)} jobs for parent_job_id={parent_job_id}")
    return {
        "statusCode": 202,
        "body": json.dumps({
            "parent_job_id": parent_job_id,
            "job_count": len(job_ids),
            "batch_size": BATCH_SIZE,
        })
    }