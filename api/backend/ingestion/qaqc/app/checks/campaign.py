"""
QAQC checks for campaign_metadata.csv

Checks (in order):
  1. Mechanical — required columns, no missing values, enum values,
                  no duplicate (campaign_name, sensor_name), castable types.
                  Driven by checks/config/campaign_metadata.json.
  2. No existing campaign_name — campaign_name must not already exist in
                                 production campaign table.
  3. No existing (campaign_name, sensor_name) — must not already exist in
                                                 production sensor_campaign.
  4. Forward campaign_sensor_set so downstream checks (wavelengths, granule)
     can validate their campaign/sensor references against this bundle.
"""

from __future__ import annotations

import pandas as pd

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import load_config, run_mechanical_checks, check_not_in_db

CONFIG = load_config("campaign_metadata")
CONFIG["_file_name"] = "campaign_metadata"


def check(context: CheckContext) -> CheckResult:
    df     = context.data["campaign_metadata"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    errors += _check_no_existing_campaigns(df, context)
    errors += _check_no_existing_sensor_campaigns(df, context)
    _forward_campaign_sensor_set(df, context)
    return CheckResult("campaign_metadata", len(df), errors, warnings)


# ── Custom checks ──────────────────────────────────────────────────────────────

def _check_no_existing_campaigns(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """campaign_name must not already exist in the production campaign table."""
    deduped = df.drop_duplicates("campaign_name")
    return check_not_in_db(
        deduped, "campaign_name", context.db["campaign_names"], "campaign_metadata"
    )


def _check_no_existing_sensor_campaigns(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """(campaign_name, sensor_name) must not already exist in production sensor_campaign."""
    errors = []
    for idx, row in df.iterrows():
        key = (row["campaign_name"], row["sensor_name"])
        if key in context.db["campaign_sensor_set"]:
            errors.append({
                "file": "campaign_metadata", "row": int(idx + 2), "column": None,
                "message": "sensor_campaign already exists in database",
            })
    return errors


# ── Forwarded output ───────────────────────────────────────────────────────────

def _forward_campaign_sensor_set(df: pd.DataFrame, context: CheckContext) -> None:
    """
    Write the set of (campaign_name, sensor_name) tuples from this bundle
    into context so wavelengths.py and granule.py can validate FK references.
    """
    context.output["campaign_sensor_set"] = set(zip(df["campaign_name"], df["sensor_name"]))
