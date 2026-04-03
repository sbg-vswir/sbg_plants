import logging
import time
import os
import boto3

logger = logging.getLogger(__name__)

dynamodb = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-west-2"))


def update_progress(job_id: str, rows_processed: int, job_table: str) -> None:
    """Write incremental row-count progress to DynamoDB during streaming."""
    dynamodb.update_item(
        TableName=job_table,
        Key={"job_id": {"S": job_id}},
        UpdateExpression="SET rows_processed = :r",
        ExpressionAttributeValues={":r": {"N": str(rows_processed)}},
    )


def finalize_job(job_id: str, bucket: str, key: str, job_table: str) -> None:
    """Generate a presigned URL and mark the job complete in DynamoDB."""
    s3 = boto3.client("s3")
    presigned_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=6 * 3600,
    )
    logger.debug("Generated presigned URL for job_id=%s", job_id)

    ttl = int(time.time()) + 24 * 3600
    dynamodb.update_item(
        TableName=job_table,
        Key={"job_id": {"S": job_id}},
        UpdateExpression="SET presigned_url = :url, #status = :s, expire_at = :ttl",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":url": {"S": presigned_url},
            ":s":   {"S": "complete"},
            ":ttl": {"N": str(ttl)},
        },
    )
    logger.debug("Marked job complete in DynamoDB for job_id=%s", job_id)


def mark_failed(job_id: str, job_table: str) -> None:
    """Mark a job as failed in DynamoDB."""
    ttl = int(time.time()) + 24 * 3600
    dynamodb.update_item(
        TableName=job_table,
        Key={"job_id": {"S": job_id}},
        UpdateExpression="SET #status = :s, expire_at = :ttl",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":s":   {"S": "failed"},
            ":ttl": {"N": str(ttl)},
        },
    )
    logger.debug("Marked job failed in DynamoDB for job_id=%s", job_id)
