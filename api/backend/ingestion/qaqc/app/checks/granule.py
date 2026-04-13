"""
QAQC checks for granule_metadata.csv

Checks (in order):
  1. Mechanical — required columns, no missing values, enum values,
                  no duplicate granule_id, castable types.
                  Driven by checks/config/granule_metadata.json.
  2. FK — each (campaign_name, sensor_name) must resolve to this bundle
          or the production database.
  3. No existing granule_id — granule_id must not already exist in the DB.
                              Prevents re-ingesting the same granule.
  4. Forward granule_id_set so plots.py can validate its granule references.
"""

from __future__ import annotations

import pandas as pd

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import (
    load_config, run_mechanical_checks,
    check_foreign_key, check_not_in_db,
)

CONFIG = load_config("granule_metadata")
CONFIG["_file_name"] = "granule_metadata"


def check(context: CheckContext) -> CheckResult:
    df     = context.data["granule_metadata"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    errors += _check_campaign_sensor_fk(df, context)
    errors += _check_no_existing_granule_ids(df, context)
    _forward_granule_id_set(df, context)
    return CheckResult("granule_metadata", len(df), errors, warnings)


# ── Custom checks ──────────────────────────────────────────────────────────────

def _check_campaign_sensor_fk(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """Each (campaign_name, sensor_name) must exist in this bundle or the DB."""
    all_sensors = (
        context.output.get("campaign_sensor_set", set())
        | context.db["campaign_sensor_set"]
    )
    return check_foreign_key(df, ["campaign_name", "sensor_name"], all_sensors, "granule_metadata")


def _check_no_existing_granule_ids(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """granule_id must not already exist in the production DB."""
    return check_not_in_db(df, "granule_id", context.db["granule_ids"], "granule_metadata")


# ── Forwarded output ───────────────────────────────────────────────────────────

def _forward_granule_id_set(df: pd.DataFrame, context: CheckContext) -> None:
    """
    Write granule_ids and GSD map from this bundle into context.

    granule_id_set  — used by plots.py to validate granule_id references.
    granule_gsd_map — used by spectra.py to build pixel footprint squares
                      for the point-in-polygon check.
    """
    context.output["granule_id_set"]  = set(df["granule_id"])
    context.output["granule_gsd_map"] = dict(zip(df["granule_id"], df["gsd"].astype(float)))
