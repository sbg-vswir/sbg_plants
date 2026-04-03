import json
import logging

from app.auth import get_claims, require_admin, handle_error, respond
from app.services import dynamo, batch as batch_svc

logger = logging.getLogger(__name__)


def list_jobs(event: dict) -> dict:
    """GET /isofit_jobs — list recent isofit parent jobs."""
    try:
        claims = get_claims(event)
        require_admin(claims)
    except Exception as err:
        return handle_error(err)

    qs = event.get("queryStringParameters") or {}
    limit = min(int(qs.get("limit", 5)), 50)

    jobs = dynamo.list_parent_jobs(limit)
    return respond(200, {"jobs": jobs})


def job_summary(event: dict, parent_job_id: str) -> dict:
    """GET /job_status/{id}?mode=summary — aggregate child batch job statuses,
    reconcile any in-flight jobs against AWS Batch, and write the derived
    parent status back to DynamoDB."""
    try:
        claims = get_claims(event)
        require_admin(claims)
    except Exception as err:
        return handle_error(err)

    items = dynamo.query_child_jobs(parent_job_id)

    # ── First pass: aggregate from DynamoDB ──────────────────────────────────
    statuses: dict[str, int] = {}
    total_pixels_processed = 0
    total_pixels_remaining = 0
    restarted_jobs: list[str] = []
    failed_jobs_pixel_ids: list = []
    in_flight: dict[str, dict] = {}  # job_id → item for running/inverting jobs

    for item in items:
        status           = item.get("status",          {}).get("S", "unknown")
        pixels_processed = int(item.get("pixels_processed", {}).get("N", 0))
        pixel_count      = int(item.get("pixel_count",      {}).get("N", 0))
        attempt          = int(item.get("attempt_number",   {}).get("N", 0))
        job_id           = item.get("job_id", {}).get("S")

        statuses[status] = statuses.get(status, 0) + 1
        total_pixels_processed += pixels_processed
        total_pixels_remaining += max(pixel_count - pixels_processed, 0)

        if attempt > 1:
            restarted_jobs.append(job_id)

        if status == "failed":
            _collect_pixel_ids(item, failed_jobs_pixel_ids)

        if status in ("running", "inverting"):
            batch_job_id = item.get("batch_job_id", {}).get("S")
            if batch_job_id:
                in_flight[batch_job_id] = item

    # ── Reconcile in-flight jobs against AWS Batch ───────────────────────────
    corrections = batch_svc.reconcile(in_flight)

    for batch_job_id, corrected in corrections.items():
        item = in_flight[batch_job_id]
        dynamo_job_id = item.get("job_id", {}).get("S")
        old_status = item.get("status", {}).get("S", "unknown")

        logger.info("Batch reconciliation: job %s (batch %s) corrected from %s to %s",
                    dynamo_job_id, batch_job_id, old_status, corrected)

        dynamo.update_job_status(dynamo_job_id, corrected)

        # Fix up aggregation counters
        statuses[old_status] = statuses.get(old_status, 0) - 1
        statuses[corrected]  = statuses.get(corrected, 0) + 1

        if corrected == "failed":
            _collect_pixel_ids(item, failed_jobs_pixel_ids)

        elif corrected == "complete":
            pixel_count      = int(item.get("pixel_count",      {}).get("N", 0))
            pixels_processed = int(item.get("pixels_processed", {}).get("N", 0))
            delta = max(pixel_count - pixels_processed, 0)
            total_pixels_remaining -= delta
            total_pixels_processed += delta

    # ── Derive and write back parent status ───────────────────────────────────
    parent_status = _derive_parent_status(statuses)
    dynamo.update_job_status(parent_job_id, parent_status)

    return respond(200, {
        "parent_job_id":          parent_job_id,
        "total_batches":          len(items),
        "statuses":               {k: v for k, v in statuses.items() if v > 0},
        "total_pixels_processed": total_pixels_processed,
        "total_pixels_remaining": max(total_pixels_remaining, 0),
        "restart_required":       len(restarted_jobs) > 0,
        "restarted_jobs":         restarted_jobs,
        "failed_jobs_pixel_ids":  failed_jobs_pixel_ids,
        "parent_status":          parent_status,
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _collect_pixel_ids(item: dict, target: list) -> None:
    raw = item.get("pixel_ids", {}).get("S")
    if raw:
        try:
            target.extend(json.loads(raw))
        except json.JSONDecodeError:
            pass


def _derive_parent_status(statuses: dict[str, int]) -> str:
    """Derive a single parent status from the aggregated child status counts."""
    active = {k for k, v in statuses.items() if v > 0}

    if not active:
        return "unknown"
    if active <= {"complete"}:
        return "complete"
    if active <= {"failed"}:
        return "failed"
    if active <= {"complete", "failed"}:
        return "partial"
    if "running" in active or "inverting" in active:
        return "running"
    if "submitted" in active:
        return "submitted"
    return "unknown"
