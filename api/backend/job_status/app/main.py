import os
import boto3
import json
from app.auth import get_claims, require_admin, handle_error

dynamodb = boto3.client("dynamodb", region_name='us-west-2')
JOB_TABLE = os.environ["JOB_TABLE"]


def lambda_handler(event, context):
    job_id = event["pathParameters"].get("job_id")
    mode = event.get("queryStringParameters", {}) or {}
    mode = mode.get("mode", "single")  # ?mode=summary

    if not job_id:
        return {"statusCode": 400, "body": "Missing job_id"}

    # -----------------------------------------
    # MODE 1: SUMMARY (parent job)
    # -----------------------------------------
    if mode == "summary":
        # Only allow superadmins for now
        try:
            claims = get_claims(event)
            require_admin(claims)
        except Exception as err:
            return handle_error(err)

        paginator = dynamodb.get_paginator("query")
        statuses = {}
        total_pixels_processed = 0
        total_pixels_remaining = 0
        restarted_jobs = []
        failed_jobs_pixel_ids = []
        total_batches = 0
        max_attempts = 10

        for page in paginator.paginate(
            TableName=JOB_TABLE,
            IndexName="parent_job_id-index",  # GSI on parent_job_id
            KeyConditionExpression="parent_job_id = :p",
            ExpressionAttributeValues={":p": {"S": job_id}},
        ):
            for item in page.get("Items", []):
                total_batches += 1
                status = item.get("status", {}).get("S", "UNKNOWN")
                pixels_processed = int(item.get("pixels_processed", {}).get("N", 0))
                batch_size = int(item.get("batch_size", {}).get("N", 0)) if "batch_size" in item else 0
                attempt = int(item.get("attempt_number", {}).get("N", 1))
                pixel_ids = item.get("pixel_ids", {}).get("L", [])

                # Count statuses
                statuses[status] = statuses.get(status, 0) + 1

                # Sum pixels processed and remaining
                total_pixels_processed += pixels_processed
                total_pixels_remaining += max(batch_size - pixels_processed, 0)

                # Check for restarted jobs
                if attempt > 1:
                    restarted_jobs.append(item.get("job_id", {}).get("S"))

                # Check for failed jobs (too many attempts)
                if attempt >= max_attempts:
                    failed_jobs_pixel_ids.extend([p.get("S") for p in pixel_ids])

        restart_required = len(restarted_jobs) > 0

        return {
            "statusCode": 200,
            "body": json.dumps({
                "parent_job_id": job_id,
                "total_batches": total_batches,
                "statuses": statuses,
                "total_pixels_processed": total_pixels_processed,
                "total_pixels_remaining": total_pixels_remaining,
                "restart_required": restart_required,
                "restarted_jobs": restarted_jobs,
                "failed_jobs_pixel_ids": failed_jobs_pixel_ids
            })
        }

    # -----------------------------------------
    # MODE 2: SINGLE BATCH JOB (existing behavior)
    # -----------------------------------------
    resp = dynamodb.get_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": job_id}}
    )

    item = resp.get("Item")
    if not item:
        return {"statusCode": 404, "body": "Job not found"}

    return {
        "statusCode": 200,
        "body": json.dumps({
            "job_id": job_id,
            "status": item.get("status", {}).get("S"),
            "rows_processed": int(item.get("rows_processed", {}).get("N", 0)),
            "presigned_url": item.get("presigned_url", {}).get("S")
        })
    }