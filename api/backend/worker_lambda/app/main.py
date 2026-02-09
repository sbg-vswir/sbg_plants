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

    for record in event.get("Records", []):
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

                # Start multipart upload
                mpu = s3.create_multipart_upload(Bucket=bucket, Key=key)
                logger.debug("Started multipart upload: %s", mpu["UploadId"])
                with conn.cursor(name="stream_cursor") as cur:
                    cur.itersize = 30000
                    cur.execute(sql, params)

                    while True:
                        rows = cur.fetchmany(cur.itersize)
                        if not rows:
                            break
                        chunk = pd.DataFrame(rows, columns=[desc[0] for desc in cur.description])

                        buffer = io.StringIO()
                        chunk.to_csv(buffer, index=False, header=(part_number==1))

                        buffer.seek(0)
                        logger.debug("Uploading part %d", part_number)
                        response = s3.upload_part(
                            Bucket=bucket,
                            Key=key,
                            PartNumber=part_number,
                            UploadId=mpu["UploadId"],
                            Body=buffer.read()
                        )
                        buffer.close()
                        buffer = None  # free memory
                        chunk = None

                        parts.append({"ETag": response["ETag"], "PartNumber": part_number})
                        logger.debug("Uploaded part %d with ETag %s", part_number, response["ETag"])
                        part_number += 1
                        rows_processed += len(rows)
                        # Update DynamoDB progress
                        dynamodb.update_item(
                            TableName=job_table,
                            Key={"job_id": {"S": job_id}},
                            UpdateExpression="SET rows_processed = :r",
                            ExpressionAttributeValues={":r": {"N": str(rows_processed)}}
                        )
                        logger.debug("Updated DynamoDB rows_processed=%d for job_id=%s", rows_processed, job_id)

                # Complete multipart upload
                logger.debug("Completing multipart upload for job_id=%s", job_id)
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
            logger.debug("Generated presigned URL for job_id=%s", job_id)

            # Add TTL (expire in 1 day)
            ttl = int(time.time()) + 1 * 24 * 3600

            # Update DynamoDB with URL, status, and TTL
            dynamodb.update_item(
                TableName=job_table,
                Key={"job_id": {"S": job_id}},
                UpdateExpression="SET presigned_url = :url, #status = :s, expire_at = :ttl",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":url": {"S": presigned_url},
                    ":s": {"S": "complete"},
                    ":ttl": {"N": str(ttl)}
                }
            )
            logger.debug("Updated DynamoDB with presigned URL and status=complete for job_id=%s", job_id)

        except Exception:
            logger.exception("Job failed for record: %s", record)
            job_id = payload.get("job_id")
            job_table = payload.get("job_table")
            if job_id and job_table:
                ttl = int(time.time()) + 1 * 24 * 3600  # 1 day for failed job
                dynamodb.update_item(
                    TableName=job_table,
                    Key={"job_id": {"S": job_id}},
                    UpdateExpression="SET #status = :s, expire_at = :ttl",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":s": {"S": "failed"},
                        ":ttl": {"N": str(ttl)}
                    }
                )
                logger.debug("Updated DynamoDB status=failed with TTL for job_id=%s", job_id)
            continue
