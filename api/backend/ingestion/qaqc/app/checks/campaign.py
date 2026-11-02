"""
QAQC checks for campaign_metadata.csv

One row per (campaign_name, sensor_name, sensor_date) — one per sensor
calibration. DOIs are submitted separately in doi.csv (see checks/doi.py).

Rows that are already in production follow the reuse-if-identical rule
(universal.check_existing_identical): identical → reused, not staged again;
different → error.

Checks (in order):
  1. Mechanical — required columns, no missing values, enum values,
                  no duplicate (campaign_name, sensor_name, sensor_date),
                  castable types. Driven by checks/config/campaign_metadata.json.
  2. Campaign columns consistent — every row of one campaign must carry the
                                   same campaign-level values.
  3. Existing campaign — reuse if identical, error if different.
  4. Existing sensor_campaign — reuse if identical (elevation_source here;
                                wavelengths are compared in wavelengths.py),
                                error if different.
  5. New sensor_campaign needs wavelengths — a calibration that is not yet in
                                             production must have its bands in
                                             wavelengths.csv.
  6. Forward campaign_sensor_set so downstream checks (wavelengths, granule,
     doi) can validate their references against this bundle.
"""

from __future__ import annotations

import pandas as pd

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import (
    load_config, run_mechanical_checks, check_existing_identical, row_key,
)
from app.db_refs import CAMPAIGN_KEY, SENSOR_CAMPAIGN_KEY

CONFIG = load_config("campaign_metadata")
CONFIG["_file_name"] = "campaign_metadata"

CAMPAIGN_COLS = {"primary_funding_source": "str", "data_repository": "str", "taxa_system": "str"}


def check(context: CheckContext) -> CheckResult:
    df     = context.data["campaign_metadata"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    if any("missing required columns" in e["message"] for e in errors):
        return CheckResult("campaign_metadata", len(df), errors, warnings)

    errors += _check_campaign_cols_consistent(df)

    camp_errors, camp_warnings, existing_campaign = check_existing_identical(
        df, CAMPAIGN_KEY, CAMPAIGN_COLS, context.db["campaign_rows"],
        "campaign_metadata", "campaign",
    )
    sc_errors, sc_warnings, existing_sc = check_existing_identical(
        df, SENSOR_CAMPAIGN_KEY, {"elevation_source": "str"},
        context.db["sensor_campaign_rows"], "campaign_metadata", "sensor_campaign",
    )
    errors   += camp_errors + sc_errors
    warnings += camp_warnings + sc_warnings
    errors   += _check_new_sensor_campaigns_have_wavelengths(df, existing_sc, context)

    context.output.setdefault("existing", {})
    context.output["existing"]["campaign"]        = existing_campaign
    context.output["existing"]["sensor_campaign"] = existing_sc
    _forward_campaign_sensor_set(df, context)
    return CheckResult("campaign_metadata", len(df), errors, warnings)


# ── Custom checks ──────────────────────────────────────────────────────────────

def _check_campaign_cols_consistent(df: pd.DataFrame) -> list[dict]:
    """
    campaign_metadata repeats the campaign columns on every sensor row; they
    must agree, since only one campaign row is stored.
    """
    errors = []
    cols = [c for c in CAMPAIGN_COLS if c in df.columns]
    for camp, grp in df.groupby("campaign_name"):
        differing = [c for c in cols if grp[c].astype(str).str.strip().nunique() > 1]
        if differing:
            errors.append({
                "file": "campaign_metadata", "row": None, "column": differing[0],
                "message": f"campaign '{camp}' has different values across rows for: {', '.join(differing)}",
            })
    return errors


def _check_new_sensor_campaigns_have_wavelengths(
    df: pd.DataFrame, existing: pd.Series, context: CheckContext,
) -> list[dict]:
    """A sensor calibration that isn't in production yet needs its bands in wavelengths.csv."""
    df_wl = context.data.get("wavelengths")
    wl_keys = set()
    if df_wl is not None and all(c in df_wl.columns for c in SENSOR_CAMPAIGN_KEY):
        wl_keys = {row_key(r, SENSOR_CAMPAIGN_KEY) for _, r in df_wl.iterrows()}

    errors = []
    for idx, row in df[~existing].iterrows():
        key = row_key(row, SENSOR_CAMPAIGN_KEY)
        if key is not None and key not in wl_keys:
            errors.append({
                "file": "campaign_metadata", "row": int(idx + 2), "column": "sensor_date",
                "message": (
                    f"(campaign_name='{key[0]}', sensor_name='{key[1]}', sensor_date='{key[2]}') "
                    f"is new but has no bands in wavelengths.csv"
                ),
            })
    return errors


# ── Forwarded output ───────────────────────────────────────────────────────────

def _forward_campaign_sensor_set(df: pd.DataFrame, context: CheckContext) -> None:
    """
    Write the set of normalized (campaign_name, sensor_name, sensor_date)
    tuples from this bundle into context so wavelengths.py, granule.py and
    doi.py can validate FK references.
    """
    keys = {row_key(r, SENSOR_CAMPAIGN_KEY) for _, r in df.iterrows()}
    context.output["campaign_sensor_set"] = keys - {None}
