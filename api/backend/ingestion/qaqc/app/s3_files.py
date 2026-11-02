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
import geopandas as gpd
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
    Download the bundle files from S3 for a given batch. Every slot is
    optional (partial bundles); a slot with no uploaded file is left out.
    Returns { slot_name: bytes }
    """
    raw = {}
    for slot, ext in get_file_slots().items():
        key = f"ingestion/{batch_id}/raw/{slot}{ext}"
        try:
            resp = s3.get_object(Bucket=BUCKET, Key=key)
        except s3.exceptions.NoSuchKey:
            logger.info("Not provided: %s", key)
            continue
        raw[slot] = resp["Body"].read()
        logger.info("Downloaded %s", key)
    return raw

def _stringify_properties(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Cast every non-geometry column to string, mirroring dtype=str on the CSVs."""
    cols = gdf.columns.drop(gdf.geometry.name)
    gdf[cols] = gdf[cols].astype(str).where(gdf[cols].notna(), "")
    return gdf

def parse_files(raw: dict) -> dict:
    """
    Parse raw bytes into DataFrames (CSVs) and a GeoDataFrame (plots).
    Returns { slot_name: DataFrame | GeoDataFrame | None } for every slot in
    the bundle config — None for a slot that wasn't provided.
    Raises ValueError if no file was provided or a file cannot be parsed.
    """
    if not raw:
        raise ValueError("No bundle files were provided")
    parsed = {}
    for slot in get_file_slots():
        if slot not in raw:
            parsed[slot] = None
            continue
        try:
            if slot == "plots":
                parsed[slot] = _stringify_properties(gpd.read_file(io.BytesIO(raw[slot])))
            else:
                parsed[slot] = pd.read_csv(io.BytesIO(raw[slot]), dtype=str).fillna("")
        except Exception as e:
            raise ValueError(f"Failed to parse {slot}: {e}") from e
    return parsed


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
