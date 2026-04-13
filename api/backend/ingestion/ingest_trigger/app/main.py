import uuid
import json
import logging
from datetime import datetime, timezone

from app.auth import get_claims, require_superadmin, get_username, respond
from app.store import (
    get_file_slots,
    get_upload_urls,
    get_replace_url,
    create_batch_record,
    invoke_qaqc,
    list_batches,
    get_batch,
    get_qaqc_report_presigned_url,
    reset_batch_for_recheck,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    path   = event.get("rawPath", "")
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    # ── Auth ──────────────────────────────────────────────────────────────────
    try:
        claims = get_claims(event)
        require_superadmin(claims)
    except PermissionError as e:
        return respond(403, {"message": str(e)})
    except Exception:
        return respond(401, {"message": "Unauthorized"})

    username = get_username(claims)
    batch_id = (event.get("pathParameters") or {}).get("batch_id")
    slot     = (event.get("pathParameters") or {}).get("slot")

    # ── Route ─────────────────────────────────────────────────────────────────

    # GET /ingest/config
    if method == "GET" and path.rstrip("/").endswith("/ingest/config"):
        return handle_get_config()

    # POST /ingest/upload-urls — request presigned S3 PUT URLs for a new batch
    if method == "POST" and path.rstrip("/").endswith("/ingest/upload-urls"):
        return handle_get_upload_urls()

    # GET /ingest — list all ingestion batches
    if method == "GET" and not batch_id:
        return handle_list_batches()

    # GET /ingest/{batch_id}
    if method == "GET" and batch_id and not slot:
        return handle_get_batch(batch_id)

    # POST /ingest — create batch record and invoke QAQC (files already in S3)
    if method == "POST" and not batch_id:
        return handle_submit(event, username)

    # GET /ingest/{batch_id}/file/{slot}/upload-url — presigned URL for file replacement
    if method == "GET" and batch_id and slot:
        return handle_get_replace_url(batch_id, slot)

    # POST /ingest/{batch_id}/recheck
    if method == "POST" and batch_id and path.rstrip("/").endswith("/recheck"):
        return handle_recheck(batch_id)

    return respond(404, {"message": "Not found"})


# ── Route handlers ────────────────────────────────────────────────────────────

def handle_get_config() -> dict:
    try:
        return respond(200, {"file_slots": get_file_slots()})
    except Exception:
        logger.exception("Failed to fetch file slots from S3")
        return respond(500, {"message": "Failed to load ingestion config"})


def handle_get_upload_urls() -> dict:
    """POST /ingest/upload-urls — generate a batch_id and presigned PUT URLs for all slots."""
    try:
        batch_id = str(uuid.uuid4())
        urls = get_upload_urls(batch_id)
        return respond(200, {"batch_id": batch_id, "upload_urls": urls})
    except Exception:
        logger.exception("Failed to generate upload URLs")
        return respond(500, {"message": "Failed to generate upload URLs"})


def handle_list_batches() -> dict:
    try:
        batches = list_batches()
        return respond(200, batches)
    except Exception:
        logger.exception("Failed to list batches")
        return respond(500, {"message": "Failed to list ingestion batches"})


def handle_get_batch(batch_id: str) -> dict:
    try:
        batch = get_batch(batch_id)
    except Exception:
        logger.exception("Failed to fetch batch batch_id=%s", batch_id)
        return respond(500, {"message": "Failed to fetch batch"})

    if not batch:
        return respond(404, {"message": "Batch not found"})

    s3_key = batch.get("qaqc_report_s3_key")
    if s3_key:
        try:
            batch["qaqc_report_presigned_url"] = get_qaqc_report_presigned_url(s3_key)
        except Exception:
            logger.exception("Failed to generate presigned URL for s3_key=%s", s3_key)

    return respond(200, batch)


def handle_submit(event: dict, username: str) -> dict:
    """POST /ingest — files are already in S3; just create the DynamoDB record and invoke QAQC."""
    try:
        body = json.loads(event.get("body") or "{}")
        batch_id = body.get("batch_id")
    except Exception:
        return respond(400, {"message": "Invalid JSON body"})

    if not batch_id:
        return respond(400, {"message": "batch_id is required"})

    uploaded_at = datetime.now(timezone.utc).isoformat()

    try:
        create_batch_record(batch_id, username, uploaded_at)
        invoke_qaqc(batch_id)
    except Exception:
        logger.exception("Failed to create batch record for batch_id=%s", batch_id)
        return respond(500, {"message": "Failed to create batch"})

    return respond(202, {
        "batch_id":    batch_id,
        "uploaded_by": username,
        "uploaded_at": uploaded_at,
    })


def handle_get_replace_url(batch_id: str, slot: str) -> dict:
    """GET /ingest/{batch_id}/file/{slot}/upload-url — presigned PUT URL for replacing one file."""
    try:
        batch = get_batch(batch_id)
    except Exception:
        logger.exception("Failed to fetch batch batch_id=%s", batch_id)
        return respond(500, {"message": "Failed to fetch batch"})

    if not batch:
        return respond(404, {"message": "Batch not found"})

    status = batch.get("status")
    if status != "QAQC_FAIL":
        return respond(409, {
            "message": f"Files can only be replaced on a QAQC_FAIL batch (current status: {status})"
        })

    try:
        url = get_replace_url(batch_id, slot)
    except ValueError as e:
        return respond(400, {"message": str(e)})
    except Exception:
        logger.exception("Failed to generate replace URL for slot '%s' batch_id=%s", slot, batch_id)
        return respond(500, {"message": "Failed to generate upload URL"})

    return respond(200, {"upload_url": url, "slot": slot, "batch_id": batch_id})


def handle_recheck(batch_id: str) -> dict:
    """POST /ingest/{batch_id}/recheck"""
    try:
        batch = get_batch(batch_id)
    except Exception:
        logger.exception("Failed to fetch batch batch_id=%s", batch_id)
        return respond(500, {"message": "Failed to fetch batch"})

    if not batch:
        return respond(404, {"message": "Batch not found"})

    status = batch.get("status")
    if status != "QAQC_FAIL":
        return respond(409, {
            "message": f"Only QAQC_FAIL batches can be rechecked (current status: {status})"
        })

    try:
        reset_batch_for_recheck(batch_id)
        invoke_qaqc(batch_id)
    except Exception:
        logger.exception("Failed to trigger recheck for batch_id=%s", batch_id)
        return respond(500, {"message": "Failed to trigger recheck"})

    logger.info("Recheck triggered for batch_id=%s", batch_id)
    return respond(202, {"message": "Recheck started", "batch_id": batch_id})
