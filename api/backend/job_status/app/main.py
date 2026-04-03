import logging
from app.auth import respond
from app.routes import isofit, single

logging.basicConfig(level=logging.INFO)


def lambda_handler(event, context):
    path   = event.get("rawPath", "")
    qs     = event.get("queryStringParameters") or {}
    job_id = (event.get("pathParameters") or {}).get("job_id")

    # GET /isofit_jobs
    if path.rstrip("/").endswith("/isofit_jobs"):
        return isofit.list_jobs(event)

    if not job_id:
        return respond(400, {"message": "Missing job_id"})

    # GET /job_status/{id}?mode=summary
    if qs.get("mode") == "summary":
        return isofit.job_summary(event, job_id)

    # GET /job_status/{id}
    return single.job_status(event, job_id)
