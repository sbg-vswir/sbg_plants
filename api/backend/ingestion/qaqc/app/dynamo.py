"""
DynamoDB operations for the QAQC lambda.
Writes status updates and QAQC report summaries back to the ingestion job record.
"""

import os
import logging
from datetime import datetime, timezone

import boto3

logger   = logging.getLogger(__name__)
dynamodb = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-west-2"))
JOB_TABLE = os.environ["JOB_TABLE"]


def update_status(batch_id: str, status: str, qaqc_report: dict = None, s3_key: str = None):
    """
    Update the DynamoDB record for a batch.

    When transitioning to QAQC_RUNNING, atomically increments run_count
    and sets last_checked_at so the frontend can display run history.

    qaqc_report: full report dict — stored as a lightweight summary (passed + row_count)
                 to keep DynamoDB item size small. Full details live in S3.
    s3_key:      S3 key of the full QAQC report JSON.
    """
    now = datetime.now(timezone.utc).isoformat()

    if status == "QAQC_RUNNING":
        # Atomic increment of run_count + record start time
        dynamodb.update_item(
            TableName=JOB_TABLE,
            Key={"job_id": {"S": batch_id}},
            UpdateExpression=(
                "SET #s = :s, last_checked_at = :ts "
                "ADD run_count :one"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s":   {"S": status},
                ":ts":  {"S": now},
                ":one": {"N": "1"},
            },
        )
        logger.info("Updated DynamoDB status=%s (run_count +1) for batch_id=%s", status, batch_id)
        return

    expr   = "SET #s = :s"
    names  = {"#s": "status"}
    values = {":s": {"S": status}}

    if qaqc_report:
        summary = {}
        for k, v in qaqc_report.items():
            if k.startswith("_"):
                # Include internal error keys as a single error message string
                msgs = [e.get("message", str(e)) if isinstance(e, dict) else str(e)
                        for e in v.get("errors", [])]
                summary[k] = {
                    "M": {
                        "passed":    {"BOOL": False},
                        "row_count": {"N": "0"},
                        "error_msg": {"S": msgs[0] if msgs else "unknown error"},
                    }
                }
            else:
                summary[k] = {
                    "M": {
                        "passed":    {"BOOL": len(v.get("errors", [])) == 0},
                        "row_count": {"N": str(v.get("row_count", 0))},
                    }
                }
        expr        += ", qaqc_report = :r"
        values[":r"] = {"M": summary}

    if s3_key:
        expr        += ", qaqc_report_s3_key = :k"
        values[":k"] = {"S": s3_key}

    dynamodb.update_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": batch_id}},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )
    logger.info("Updated DynamoDB status=%s for batch_id=%s", status, batch_id)
