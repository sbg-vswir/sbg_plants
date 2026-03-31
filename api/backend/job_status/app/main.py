import os
import boto3
import json
from app.auth import get_claims, require_admin, handle_error, respond

dynamodb = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-west-2"))
JOB_TABLE = os.environ["JOB_TABLE"]


def lambda_handler(event, context):
    path       = event.get("rawPath", "")
    job_id     = (event.get("pathParameters") or {}).get("job_id")
    qs         = event.get("queryStringParameters") or {}
    mode       = qs.get("mode", "single")

    # -----------------------------------------
    # GET /isofit_jobs  — list parent jobs
    # -----------------------------------------
    if path.rstrip("/").endswith("/isofit_jobs"):
        try:
            claims = get_claims(event)
            require_admin(claims)
        except Exception as err:
            return handle_error(err)

        limit = min(int(qs.get("limit", 5)), 50)

        resp = dynamodb.query(
            TableName=JOB_TABLE,
            IndexName="job_type-index",
            KeyConditionExpression="job_type = :t",
            ExpressionAttributeValues={":t": {"S": "isofit_parent"}},
            ScanIndexForward=False,   # newest first (descending by created_at)
            Limit=limit,
        )

        jobs = [
            {
                "job_id":       item.get("job_id",       {}).get("S"),
                "status":       item.get("status",       {}).get("S"),
                "submitted_by": item.get("submitted_by", {}).get("S"),
                "created_at":   item.get("created_at",   {}).get("S"),
            }
            for item in resp.get("Items", [])
        ]
        return respond(200, {"jobs": jobs})

    if not job_id:
        return respond(400, {"message": "Missing job_id"})

    # -----------------------------------------
    # MODE 1: SUMMARY (parent job)
    # -----------------------------------------
    if mode == "summary":
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

        for page in paginator.paginate(
            TableName=JOB_TABLE,
            IndexName="parent_job_id-index",
            KeyConditionExpression="parent_job_id = :p",
            ExpressionAttributeValues={":p": {"S": job_id}},
        ):
            for item in page.get("Items", []):
                total_batches += 1
                status           = item.get("status", {}).get("S", "UNKNOWN")
                pixels_processed = int(item.get("pixels_processed", {}).get("N", 0))
                pixel_count      = int(item.get("pixel_count", {}).get("N", 0))
                attempt          = int(item.get("attempt_number", {}).get("N", 0))

                statuses[status] = statuses.get(status, 0) + 1
                total_pixels_processed += pixels_processed
                total_pixels_remaining += max(pixel_count - pixels_processed, 0)

                if attempt > 1:
                    restarted_jobs.append(item.get("job_id", {}).get("S"))

                # pixel_ids is stored as a JSON-encoded string
                if status == "failed":
                    raw = item.get("pixel_ids", {}).get("S")
                    if raw:
                        try:
                            failed_jobs_pixel_ids.extend(json.loads(raw))
                        except json.JSONDecodeError:
                            pass

        return respond(200, {
            "parent_job_id":         job_id,
            "total_batches":         total_batches,
            "statuses":              statuses,
            "total_pixels_processed": total_pixels_processed,
            "total_pixels_remaining": total_pixels_remaining,
            "restart_required":      len(restarted_jobs) > 0,
            "restarted_jobs":        restarted_jobs,
            "failed_jobs_pixel_ids": failed_jobs_pixel_ids,
        })

    # -----------------------------------------
    # MODE 2: SINGLE JOB
    # -----------------------------------------
    resp = dynamodb.get_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": job_id}}
    )

    item = resp.get("Item")
    if not item:
        return respond(404, {"message": "Job not found"})

    return respond(200, {
        "job_id":        job_id,
        "status":        item.get("status", {}).get("S"),
        "rows_processed": int(item.get("rows_processed", {}).get("N", 0)),
        "presigned_url": item.get("presigned_url", {}).get("S"),
    })