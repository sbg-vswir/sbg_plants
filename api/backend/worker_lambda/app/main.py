import logging
import os

from app.db import get_connection
from app.record_parser import parse_record
from app.s3_upload import stream_to_s3
from app.job_store import finalize_job, mark_failed

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


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
