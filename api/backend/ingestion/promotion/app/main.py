import logging

from app.auth import get_claims, require_superadmin, respond
from app.db import get_connection
from app.dynamo import get_batch, mark_promoted
from app.promote import promote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def lambda_handler(event, context):

    # ── Auth ──────────────────────────────────────────────────────────────────
    try:
        claims = get_claims(event)
        require_superadmin(claims)
    except PermissionError as e:
        return respond(403, {"message": str(e)})
    except Exception:
        return respond(401, {"message": "Unauthorized"})

    batch_id = (event.get("pathParameters") or {}).get("batch_id")
    if not batch_id:
        return respond(400, {"message": "Missing batch_id"})

    # ── Validate batch is ready to promote ────────────────────────────────────
    item = get_batch(batch_id)
    if not item:
        return respond(404, {"message": "Batch not found"})

    status = item.get("status", {}).get("S")
    if status != "QAQC_PASS":
        return respond(409, {"message": f"Batch status is '{status}', expected QAQC_PASS"})

    # ── Promote staging → production ──────────────────────────────────────────
    logger.info("Promoting batch_id=%s", batch_id)
    try:
        conn = get_connection()
        promote(conn, batch_id)
    except Exception as e:
        logger.exception("Promotion failed for batch_id=%s", batch_id)
        return respond(500, {"message": f"Promotion failed: {e}"})

    # ── Mark complete ─────────────────────────────────────────────────────────
    promoted_at = mark_promoted(batch_id)
    logger.info("Promotion complete for batch_id=%s", batch_id)
    return respond(200, {"batch_id": batch_id, "status": "PROMOTED", "promoted_at": promoted_at})
