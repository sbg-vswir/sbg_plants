import os
import boto3

dynamodb = boto3.client("dynamodb")
JOB_TABLE = os.environ["JOB_TABLE"]

def lambda_handler(event, context):
    job_id = event["pathParameters"].get("job_id")

    if not job_id:
        return {"statusCode": 400, "body": "Missing job_id"}

    resp = dynamodb.get_item(
        TableName=JOB_TABLE,
        Key={"job_id": {"S": job_id}}
    )
    item = resp.get("Item")
    if not item:
        return {"statusCode": 404, "body": "Job not found"}

    return {
        "statusCode": 200,
        "body": {
            "status": item.get("status", {}).get("S"),
            "rows_processed": int(item.get("rows_processed", {}).get("N", 0)),
            "presigned_url": item.get("presigned_url", {}).get("S")
        }
    }
