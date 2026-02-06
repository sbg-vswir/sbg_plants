import io
import logging
import json
import os
import boto3
import pandas as pd
from app.db import get_connection
import time

logger = logging.getLogger("lambda_handler")
logger.setLevel(logging.DEBUG)

s3 = boto3.client("s3")
dynamodb = boto3.client("dynamodb", region_name="us-west-2")

def lambda_handler(event, context):
    bucket = os.environ['S3_BUCKET']
    job_table = os.environ['JOB_TABLE']

    for record in event["Records"]:
        payload = {}
        try:
            payload = json.loads(record["body"])
            debug = payload.get("debug", False)
            if debug:
                logger.setLevel(logging.DEBUG)
                logger.debug("Debug logging ENABLED for this request")

            job_id = payload["job_id"]
            sql = payload["sql_query"]
            params = payload.get("params", [])
            key = f"exports/{job_id}.csv"

            logger.debug("Processing job_id=%s, s3_key=%s", job_id, key)

            # -----------------------------
            # Open DB connection
            # -----------------------------
            with get_connection() as conn:
                logger.debug("Connected to the database!")

                # -----------------------------
                # Stream SQL results with pandas
                # -----------------------------
                rows_processed = 0
                parts = []
                part_number = 1
                buffer = io.StringIO()

                # Start multipart upload
                mpu = s3.create_multipart_upload(Bucket=bucket, Key=key)

                for chunk in pd.read_sql(sql, conn, params=params, chunksize=10000):
                    rows_processed += len(chunk)
                    chunk.to_csv(buffer, index=False, header=(part_number==1))

                    # Upload if buffer > 5 MB
                    if buffer.tell() > 5 * 1024 * 1024:
                        buffer.seek(0)
                        logger.debug("Uploading part %d, rows so far=%d", part_number, rows_processed)
                        response = s3.upload_part(
                            Bucket=bucket,
                            Key=key,
                            PartNumber=part_number,
                            UploadId=mpu["UploadId"],
                            Body=buffer.read()
                        )
                        parts.append({"ETag": response["ETag"], "PartNumber": part_number})
                        part_number += 1
                        buffer = io.StringIO()  # reset buffer

                        # Update DynamoDB progress
                        dynamodb.update_item(
                            TableName=job_table,
                            Key={"job_id": {"S": job_id}},
                            UpdateExpression="SET rows_processed = :r",
                            ExpressionAttributeValues={":r": {"N": str(rows_processed)}}
                        )

                        logger.debug("Uploaded part %d for job_id=%s, total rows=%d", part_number-1, job_id, rows_processed)

                # Upload remaining data
                if buffer.tell() > 0:
                    buffer.seek(0)
                    logger.debug("Uploading final part %d, rows=%d", part_number, rows_processed)
                    response = s3.upload_part(
                        Bucket=bucket,
                        Key=key,
                        PartNumber=part_number,
                        UploadId=mpu["UploadId"],
                        Body=buffer.read()
                    )
                    parts.append({"ETag": response["ETag"], "PartNumber": part_number})
                    logger.debug("part_uploaded %d, rows=%d", part_number, rows_processed)
                    # # Update DynamoDB progress
                    # dynamodb.update_item(
                    #     TableName=job_table,
                    #     Key={"job_id": {"S": job_id}},
                    #     UpdateExpression="SET rows_processed = :r",
                    #     ExpressionAttributeValues={":r": {"N": str(rows_processed)}}
                    # )
                    
                    ttl = int(time.time()) + 1*24*3600  # expire in 1 days
                    dynamodb.update_item(
                        TableName=job_table,
                        Key={"job_id": {"S": job_id}},
                        UpdateExpression="SET rows_processed = :r, expire_at = :ttl",
                        ExpressionAttributeValues={
                            ":r": {"N": str(rows_processed)},
                            ":ttl": {"N": str(ttl)}
                        }
                    )
                    logger.debug("db updated")

                # Complete multipart upload
                logger.debug("starting final upload")
                s3.complete_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=mpu["UploadId"],
                    MultipartUpload={"Parts": parts}
                )
                logger.debug("Multipart upload complete for job_id=%s", job_id)

            # -----------------------------
            # Generate Presigned URL
            # -----------------------------
            presigned_url = s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=6*3600
            )

            dynamodb.update_item(
                TableName=job_table,
                Key={"job_id": {"S": job_id}},
                UpdateExpression="SET presigned_url = :url, #status = :s",
                ExpressionAttributeNames={
                    "#status": "status"  # Add this!
                },
                ExpressionAttributeValues={
                    ":url": {"S": presigned_url}, 
                    ":s": {"S": "complete"}
                }
            )
            logger.debug("DynamoDB updated with presigned URL for job_id=%s", job_id)

        except Exception:
            logger.exception("Job failed for record: %s", record)
            job_id = payload.get("job_id")
            job_table = payload.get("job_table")
            if job_id and job_table:
                dynamodb.update_item(
                    TableName=job_table,
                    Key={"job_id": {"S": job_id}},
                    UpdateExpression="SET #status = :s",
                    ExpressionAttributeNames={
                        "#status": "status"
                    },
                    ExpressionAttributeValues={
                        ":s": {"S": "failed"}
                    }
                )
            continue
