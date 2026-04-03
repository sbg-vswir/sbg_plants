import os
import boto3

batch = boto3.client("batch", region_name=os.environ.get("AWS_REGION", "us-west-2"))

# Map AWS Batch terminal statuses to our DynamoDB status values.
# Non-terminal Batch statuses (SUBMITTED, PENDING, RUNNABLE, STARTING, RUNNING)
# are intentionally excluded — we only correct jobs that Batch has finalized.
_BATCH_TO_STATUS = {
    "SUCCEEDED": "complete",
    "FAILED":    "failed",
}


def reconcile(in_flight: dict[str, dict]) -> dict[str, str]:
    """
    Check AWS Batch for the real status of any jobs still marked
    running or inverting in DynamoDB.

    Args:
        in_flight: {job_id: dynamo_item} for all running/inverting jobs

    Returns:
        {job_id: corrected_status} — only jobs whose status needs updating
    """
    if not in_flight:
        return {}

    ids = list(in_flight.keys())
    corrections = {}

    # describe_jobs accepts at most 100 IDs per call
    for i in range(0, len(ids), 100):
        resp = batch.describe_jobs(jobs=ids[i:i + 100])
        for job in resp.get("jobs", []):
            corrected = _BATCH_TO_STATUS.get(job.get("status"))
            if corrected:
                corrections[job["jobId"]] = corrected

    return corrections
