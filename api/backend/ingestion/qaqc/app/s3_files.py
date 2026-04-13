"""
S3 operations for the QAQC lambda:
- Fetching bundle config (file slots)
- Downloading raw bundle files
- Parsing files into DataFrames / dicts
- Writing the QAQC report back to S3
"""

import io
import json
import os
import logging
import boto3
import pandas as pd
from datetime import datetime, timezone
from functools import lru_cache

logger = logging.getLogger(__name__)

s3     = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-2"))
BUCKET = os.environ["CONFIG_BUCKET"]

BUNDLE_CONFIG_KEY = "ingestion/bundle_config.json"


@lru_cache(maxsize=1)
def get_file_slots() -> dict:
    """
    Fetch bundle file slot definitions from S3.
    Cached per warm Lambda instance.
    Returns { slot_name: extension } e.g. { "spectra": ".csv" }
    """
    resp   = s3.get_object(Bucket=BUCKET, Key=BUNDLE_CONFIG_KEY)
    config = json.loads(resp["Body"].read())
    return config["file_slots"]


def download_raw_files(batch_id: str) -> dict:
    """
    Download all bundle files from S3 for a given batch.
    Returns { slot_name: bytes }
    """
    raw = {}
    for slot, ext in get_file_slots().items():
        key = f"ingestion/{batch_id}/raw/{slot}{ext}"
        resp = s3.get_object(Bucket=BUCKET, Key=key)
        raw[slot] = resp["Body"].read()
        logger.info("Downloaded %s", key)
    return raw


def parse_files(raw: dict) -> tuple:
    """
    Parse raw bytes into DataFrames and a GeoJSON dict.
    Returns (df_campaign, df_wl, df_granule, df_traits, df_spectra, geojson_data)
    Raises ValueError if any file cannot be parsed.
    """
    try:
        df_campaign = pd.read_csv(io.BytesIO(raw["campaign_metadata"]), dtype=str).fillna("")
        df_wl       = pd.read_csv(io.BytesIO(raw["wavelengths"]),       dtype=str).fillna("")
        df_granule  = pd.read_csv(io.BytesIO(raw["granule_metadata"]),  dtype=str).fillna("")
        df_traits   = pd.read_csv(io.BytesIO(raw["traits"]),            dtype=str).fillna("")
        df_spectra  = pd.read_csv(io.BytesIO(raw["spectra"]),           dtype=str).fillna("")
        geojson     = json.loads(raw["plots"])
    except Exception as e:
        raise ValueError(f"Failed to parse bundle files: {e}") from e

    return df_campaign, df_wl, df_granule, df_traits, df_spectra, geojson


def write_report(batch_id: str, status: str, qaqc_report: dict) -> str:
    """
    Write the full QAQC report JSON to S3.
    Returns the S3 key.
    """
    key = f"ingestion/{batch_id}/qaqc_report.json"
    full_report = {
        "batch_id":   batch_id,
        "status":     status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "files":      qaqc_report,
    }
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(full_report, indent=2).encode(),
        ContentType="application/json",
    )
    logger.info("Wrote QAQC report to s3://%s/%s", BUCKET, key)
    return key
