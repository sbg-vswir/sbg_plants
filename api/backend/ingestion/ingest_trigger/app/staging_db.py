import os
import logging
import json
import boto3
import psycopg2

logger = logging.getLogger(__name__)

REGION            = os.environ.get("AWS_REGION", "us-west-2")
STAGING_DB_SECRET = os.environ.get("STAGING_DB_SECRET_ARN")

# Reverse dependency order for safe deletion — same list used by
# qaqc/app/staging.py::STAGING_TABLES, promotion/app/promote.py::_cleanup_staging,
# and rejection/app/main.py::STAGING_TABLES (kept in sync manually; these are
# separate Lambda deployments with no shared package today).
STAGING_TABLES = [
    "extracted_spectra", "pixel", "leaf_traits", "sample",
    "insitu_plot_event", "plot_raster_intersect", "plot",
    "plot_shape", "granule", "sensor_campaign", "doi", "campaign",
]


def get_staging_connection():
    """
    Open a fresh connection to vswir_plants_staging using the same
    ingestion_staging credentials the qaqc/rejection Lambdas use.
    Not cached — this Lambda is short-lived and this is only used on delete.
    """
    secrets = boto3.client("secretsmanager", region_name=REGION)
    creds   = json.loads(secrets.get_secret_value(SecretId=STAGING_DB_SECRET)["SecretString"])
    return psycopg2.connect(
        host=creds["host"],
        port=creds.get("port", 5432),
        dbname=creds["dbname"],
        user=creds["username"],
        password=creds["password"],
        connect_timeout=10,
    )


def purge_staging(batch_id: str) -> None:
    """
    Delete any staging rows for batch_id, in reverse dependency order,
    inside a single transaction (commit on success, rollback on failure).
    Safe to call even if nothing is staged for this batch (e.g. a REJECTED
    batch already had its staging rows cleaned up by the rejection Lambda,
    or a PROMOTED batch — which can never reach here, see NON_DELETABLE_STATUSES
    in main.py) — every DELETE is then a no-op.
    """
    conn = get_staging_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for table in STAGING_TABLES:
                    cur.execute(
                        f"DELETE FROM vswir_plants_staging.{table} WHERE batch_id = %s",
                        (batch_id,),
                    )
        logger.info("Purged staging rows for batch_id=%s", batch_id)
    finally:
        conn.close()
