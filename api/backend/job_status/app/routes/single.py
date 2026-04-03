from app.auth import respond
from app.services import dynamo


def job_status(event: dict, job_id: str) -> dict:
    """GET /job_status/{id} — single job lookup used by the spectra extraction flow."""
    item = dynamo.get_job(job_id)

    if not item:
        return respond(404, {"message": "Job not found"})

    return respond(200, {
        "job_id":         job_id,
        "status":         item.get("status",        {}).get("S"),
        "rows_processed": int(item.get("rows_processed", {}).get("N", 0)),
        "presigned_url":  item.get("presigned_url", {}).get("S"),
    })
