import os
import boto3
from datetime import datetime, timezone

dynamodb = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-west-2"))
JOB_TABLE = os.environ["JOB_TABLE"]


def list_parent_jobs(limit: int) -> list[dict]:
    """Query the job_type-index GSI for isofit_parent jobs, newest first."""
    resp = dynamodb.query(
        TableName=JOB_TABLE,
        IndexName="job_type-index",
        KeyConditionExpression="job_type = :t",
        ExpressionAttributeValues={":t": {"S": "isofit_parent"}},
        ScanIndexForward=False,
        Limit=limit,
    )
    return [
        {
            "job_id":       item.get("job_id",       {}).get("S"),
            "status":       item.get("status",       {}).get("S"),
            "submitted_by": item.get("submitted_by", {}).get("S"),
            "created_at":   item.get("created_at",   {}).get("S"),
        }
        for item in resp.get("Items", [])
    ]


def query_child_jobs(parent_job_id: str) -> list[dict]:
    """Page through all child batch records for a parent job."""
    paginator = dynamodb.get_paginator("query")
    items = []
    for page in paginator.paginate(
        TableName=JOB_TABLE,
        IndexName="parent_job_id-index",
        KeyConditionExpression="parent_job_id = :p",
        ExpressionAttributeValues={":p": {"S": parent_job_id}},
    ):
        items.extend(page.get("Items", []))
    return items


def get_job(job_id: str) -> dict | None:
    """Fetch a single job record by primary key."""
    resp = dynamodb.get_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": job_id}},
    )
    return resp.get("Item")


def update_job_status(job_id: str, status: str) -> None:
    """Write a corrected or derived status back to a job record."""
    dynamodb.update_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": job_id}},
        UpdateExpression="SET #s = :s, updated_at = :ts",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s":  {"S": status},
            ":ts": {"S": datetime.now(timezone.utc).isoformat()},
        },
    )
