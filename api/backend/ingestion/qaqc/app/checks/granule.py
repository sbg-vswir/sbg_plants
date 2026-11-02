"""
QAQC checks for granule_metadata.csv

Checks (in order):
  1. Mechanical — required columns, no missing values, enum values,
                  no duplicate granule_id, castable types.
                  Driven by checks/config/granule_metadata.json.
  2. FK — each (campaign_name, sensor_name, sensor_date) must resolve to
          this bundle or the production database.
  3. Sensor date (warning) — sensor_date after acquisition_date means the
                             granule claims a calibration that didn't exist
                             yet when it was flown.
  4. No existing granule_id — granule_id must not already exist in the DB.
                              Prevents re-ingesting the same granule.
  5. Forward granule_id_set, granule_gsd_map and granule_sensor_map for
     plots.py and spectra.py.
"""

from __future__ import annotations

import pandas as pd

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import (
    load_config, run_mechanical_checks,
    check_not_in_db, normalize, row_key,
)
from app.db_refs import SENSOR_CAMPAIGN_KEY

CONFIG = load_config("granule_metadata")
CONFIG["_file_name"] = "granule_metadata"


def check(context: CheckContext) -> CheckResult:
    df     = context.data["granule_metadata"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    if any("missing required columns" in e["message"] for e in errors):
        return CheckResult("granule_metadata", len(df), errors, warnings)
    errors   += _check_campaign_sensor_fk(df, context)
    warnings += _check_sensor_date_before_acquisition(df)
    errors   += _check_no_existing_granule_ids(df, context)
    _forward_granule_id_set(df, context)
    return CheckResult("granule_metadata", len(df), errors, warnings)


# ── Custom checks ──────────────────────────────────────────────────────────────

def _check_campaign_sensor_fk(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """Each (campaign_name, sensor_name, sensor_date) must exist in this bundle or the DB."""
    all_sensors = (
        context.output.get("campaign_sensor_set", set())
        | context.db["campaign_sensor_set"]
    )
    errors = []
    for idx, row in df.iterrows():
        key = row_key(row, SENSOR_CAMPAIGN_KEY)
        if key is not None and key not in all_sensors:
            errors.append({
                "file": "granule_metadata", "row": int(idx + 2), "column": "sensor_date",
                "message": (
                    f"(campaign_name='{row['campaign_name']}', sensor_name='{row['sensor_name']}', "
                    f"sensor_date='{row['sensor_date']}') not found in campaign_metadata or database"
                ),
            })
    return errors


def _check_sensor_date_before_acquisition(df: pd.DataFrame) -> list[dict]:
    """Warning: a granule should use a calibration that took effect on or before it was flown."""
    warnings = []
    for idx, row in df.iterrows():
        sensor_date = normalize(row["sensor_date"], "date")
        acquired    = normalize(row["acquisition_date"], "date")
        if sensor_date and acquired and len(sensor_date) == len(acquired) == 10 and sensor_date > acquired:
            warnings.append({
                "file": "granule_metadata", "row": int(idx + 2), "column": "sensor_date",
                "message": f"sensor_date {sensor_date} is after acquisition_date {acquired}",
            })
    return warnings


def _check_no_existing_granule_ids(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """granule_id must not already exist in the production DB."""
    return check_not_in_db(df, "granule_id", context.db["granule_ids"], "granule_metadata")


# ── Forwarded output ───────────────────────────────────────────────────────────

def _forward_granule_id_set(df: pd.DataFrame, context: CheckContext) -> None:
    """
    Write granule_ids and GSD map from this bundle into context.

    granule_id_set     — used by plots.py to validate granule_id references.
    granule_gsd_map    — used by spectra.py to build pixel footprint squares
                         for the point-in-polygon check.
    granule_sensor_map — granule_id → (campaign, sensor, sensor_date), used by
                         spectra.py to look up the expected band count.
    """
    context.output["granule_id_set"]     = set(df["granule_id"])
    context.output["granule_gsd_map"]    = dict(zip(df["granule_id"], pd.to_numeric(df["gsd"], errors="coerce")))
    context.output["granule_sensor_map"] = {
        row["granule_id"]: row_key(row, SENSOR_CAMPAIGN_KEY) for _, row in df.iterrows()
    }
