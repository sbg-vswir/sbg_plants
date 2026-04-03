import logging
import boto3
import os

from app.csv_builder import build_spectral_csv, build_standard_csv, dataframe_to_csv_buffer
from app.job_store import update_progress

logger = logging.getLogger(__name__)

s3 = boto3.client("s3")
CHUNK_SIZE = 30000


def stream_to_s3(
    conn,
    sql: str,
    params: list,
    spectral_metadata: dict | None,
    bucket: str,
    key: str,
    job_id: str,
    job_table: str,
) -> None:
    """
    Execute sql via a server-side cursor, stream results as CSV chunks
    to S3 via multipart upload, and write DynamoDB progress updates.

    Raises on any error — the multipart upload is aborted in a finally block.
    """
    mpu = s3.create_multipart_upload(Bucket=bucket, Key=key)
    logger.debug("Started multipart upload: %s", mpu["UploadId"])

    parts          = []
    part_number    = 1
    rows_processed = 0
    header_written = False

    try:
        with conn.cursor(name="stream_cursor") as cur:
            cur.itersize = CHUNK_SIZE
            cur.execute(sql, params)

            while True:
                rows = cur.fetchmany(cur.itersize)
                if not rows:
                    break

                if spectral_metadata:
                    chunk = build_spectral_csv(rows, cur.description, spectral_metadata)
                else:
                    chunk = build_standard_csv(rows, cur.description)

                buffer = dataframe_to_csv_buffer(chunk, write_header=not header_written)
                header_written = True

                response = s3.upload_part(
                    Bucket=bucket,
                    Key=key,
                    PartNumber=part_number,
                    UploadId=mpu["UploadId"],
                    Body=buffer.read(),
                )
                buffer.close()

                parts.append({"ETag": response["ETag"], "PartNumber": part_number})
                logger.debug("Uploaded part %d — ETag %s", part_number, response["ETag"])

                part_number    += 1
                rows_processed += len(rows)
                update_progress(job_id, rows_processed, job_table)
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
