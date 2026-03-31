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
dynamodb = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-west-2"))


# -----------------------------------------------------------------------
# CSV builders
# -----------------------------------------------------------------------

def build_spectral_csv(rows, col_descriptions, spectral_metadata):
    campaign_name     = spectral_metadata["campaign_name"]
    sensor_name       = spectral_metadata["sensor_name"]
    wavelength_center = spectral_metadata["wavelength_center"]
    fwhm              = spectral_metadata["fwhm"]

    col_names     = [desc[0] for desc in col_descriptions]
    pixel_id_idx  = col_names.index("pixel_id")
    radiance_idx  = col_names.index("radiance")

    fixed_cols  = [("campaign_name", ""), ("sensor_name", ""), ("pixel_id", "")]
    spectral_cols = list(zip(wavelength_center, fwhm))
    multi_index = pd.MultiIndex.from_tuples(fixed_cols + spectral_cols)

    data = []
    for row in rows:
        pixel_id = row[pixel_id_idx]
        radiance = row[radiance_idx]
        data.append([campaign_name, sensor_name, pixel_id] + list(radiance))

    return pd.DataFrame(data, columns=multi_index)


def build_standard_csv(rows, col_descriptions):
    return pd.DataFrame(rows, columns=[desc[0] for desc in col_descriptions])


def chunk_to_csv(df, write_header):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=write_header)
    buffer.seek(0)
    return buffer


# -----------------------------------------------------------------------
# Record parsing
# -----------------------------------------------------------------------

def parse_record(record):
    """
    Parse an SQS record body and return a normalised payload dict.
    Raises KeyError if required fields are missing.
    """
    payload = json.loads(record["body"])

    job_id           = payload["job_id"]
    sql              = payload["sql_query"]
    params           = payload.get("params", [])
    debug            = payload.get("debug", False)
    spectral_metadata = payload.get("spectral_metadata")

    if spectral_metadata:
        campaign_name = spectral_metadata["campaign_name"]
        sensor_name   = spectral_metadata["sensor_name"]
        key = f"exports/{campaign_name}_{sensor_name}_{job_id}.csv"
    else:
        key = f"exports/{job_id}.csv"

    return {
        "job_id":            job_id,
        "sql":               sql,
        "params":            params,
        "debug":             debug,
        "spectral_metadata": spectral_metadata,
        "key":               key,
    }


# -----------------------------------------------------------------------
# S3 streaming upload
# -----------------------------------------------------------------------

def stream_to_s3(conn, sql, params, spectral_metadata, bucket, key, job_id, job_table):
    """
    Execute sql via a server-side cursor, stream results as CSV chunks
    to S3 via multipart upload, and write DynamoDB progress updates.

    Returns the list of completed S3 parts.
    Raises on any error — multipart upload is aborted in a finally block.
    """
    mpu = s3.create_multipart_upload(Bucket=bucket, Key=key)
    logger.debug("Started multipart upload: %s", mpu["UploadId"])

    parts          = []
    part_number    = 1
    rows_processed = 0
    header_written = False

    try:
        with conn.cursor(name="stream_cursor") as cur:
            cur.itersize = 30000
            cur.execute(sql, params)

            while True:
                rows = cur.fetchmany(cur.itersize)
                if not rows:
                    break

                if spectral_metadata:
                    chunk = build_spectral_csv(rows, cur.description, spectral_metadata)
                else:
                    chunk = build_standard_csv(rows, cur.description)

                buffer = chunk_to_csv(chunk, write_header=not header_written)
                header_written = True

                logger.debug("Uploading part %d", part_number)
                response = s3.upload_part(
                    Bucket=bucket,
                    Key=key,
                    PartNumber=part_number,
                    UploadId=mpu["UploadId"],
                    Body=buffer.read(),
                )
                buffer.close()

                parts.append({"ETag": response["ETag"], "PartNumber": part_number})
                logger.debug("Uploaded part %d with ETag %s", part_number, response["ETag"])

                part_number    += 1
                rows_processed += len(rows)

                dynamodb.update_item(
                    TableName=job_table,
                    Key={"job_id": {"S": job_id}},
                    UpdateExpression="SET rows_processed = :r",
                    ExpressionAttributeValues={":r": {"N": str(rows_processed)}},
                )
                logger.debug("Progress: rows_processed=%d job_id=%s", rows_processed, job_id)

        if not parts:
            raise ValueError(f"Query returned no rows for job_id={job_id}")

        s3.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=mpu["UploadId"],
            MultipartUpload={"Parts": parts},
        )
        logger.debug("Multipart upload complete for job_id=%s", job_id)

    except Exception:
        logger.exception("Aborting multipart upload for job_id=%s", job_id)
        try:
            s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=mpu["UploadId"])
        except Exception:
            logger.exception("Failed to abort multipart upload for job_id=%s", job_id)
        raise

    return parts


# -----------------------------------------------------------------------
# Job finalisation
# -----------------------------------------------------------------------

def finalize_job(job_id, bucket, key, job_table):
    """Generate a presigned URL and mark the job complete in DynamoDB."""
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


def mark_failed(job_id, job_table):
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


# -----------------------------------------------------------------------
# Lambda entry point
# -----------------------------------------------------------------------

def lambda_handler(event, context):
    bucket    = os.environ["S3_BUCKET"]
    job_table = os.environ["JOB_TABLE"]

    for record in event.get("Records", []):
        job_id = None
        try:
            parsed = parse_record(record)

            if parsed["debug"]:
                logger.setLevel(logging.DEBUG)
                logger.debug("Debug logging ENABLED for this request")

            job_id = parsed["job_id"]
            logger.debug("Processing job_id=%s s3_key=%s", job_id, parsed["key"])

            with get_connection() as conn:
                stream_to_s3(
                    conn=conn,
                    sql=parsed["sql"],
                    params=parsed["params"],
                    spectral_metadata=parsed["spectral_metadata"],
                    bucket=bucket,
                    key=parsed["key"],
                    job_id=job_id,
                    job_table=job_table,
                )

            finalize_job(job_id, bucket, parsed["key"], job_table)

        except Exception:
            logger.exception("Job failed for job_id=%s", job_id)
            if job_id:
                mark_failed(job_id, job_table)
            continue
