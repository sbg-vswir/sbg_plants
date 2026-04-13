import os
import logging
import boto3
from datetime import datetime, timezone

logger   = logging.getLogger(__name__)
dynamodb = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-west-2"))
JOB_TABLE = os.environ["JOB_TABLE"]


def get_batch(batch_id: str) -> dict | None:
    """Fetch a batch record by batch_id. Returns None if not found."""
    resp = dynamodb.get_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": batch_id}},
    )
    return resp.get("Item")


def mark_promoted(batch_id: str) -> str:
    """Mark the batch as PROMOTED and record the promotion timestamp."""
    promoted_at = datetime.now(timezone.utc).isoformat()
    dynamodb.update_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": batch_id}},
        UpdateExpression="SET #s = :s, promoted_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": {"S": "PROMOTED"},
            ":t": {"S": promoted_at},
        },
    )
    logger.info("Marked batch_id=%s as PROMOTED", batch_id)
    return promoted_at
