import json


def parse_record(record: dict) -> dict:
    """
    Parse a single SQS record body into a normalised payload dict.

    Returns:
        {
            job_id:            str
            sql:               str
            params:            list
            debug:             bool
            spectral_metadata: dict | None
            key:               str   — S3 object key for the output CSV
        }

    Raises KeyError if required fields are missing.
    """
    payload = json.loads(record["body"])

    job_id            = payload["job_id"]
    sql               = payload["sql_query"]
    params            = payload.get("params", [])
    debug             = payload.get("debug", False)
    spectral_metadata = payload.get("spectral_metadata")

    if spectral_metadata:
        campaign_name = spectral_metadata["campaign_name"]
        sensor_name   = spectral_metadata["sensor_name"]
        spectral_col  = spectral_metadata.get("spectral_column", "radiance")
        key = f"exports/{campaign_name}_{sensor_name}_{spectral_col}_{job_id}.csv"
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
