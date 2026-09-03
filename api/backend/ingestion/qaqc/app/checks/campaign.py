"""
QAQC checks for campaign_metadata.csv

One row per (campaign_name, sensor_name, doi) — a campaign with several DOIs
fans out into several rows sharing the same campaign/sensor metadata.

Checks (in order):
  1. Mechanical — required columns, no missing values, enum values,
                  no duplicate (campaign_name, sensor_name, doi), castable
                  types. Driven by checks/config/campaign_metadata.json.
  2. No existing campaign_name — campaign_name must not already exist in
                                 production campaign table.
  3. No existing (campaign_name, sensor_name) — must not already exist in
                                                 production sensor_campaign.
  4. No existing doi — doi must not already exist in production doi table.
  5. No duplicate doi within the bundle — doi is a global PK (not scoped to
     campaign), so a doi repeated under a different campaign/sensor would
     slip past the mechanical pk_cols check above.
  6. Forward campaign_sensor_set and doi_set so downstream checks
     (wavelengths, granule, traits) can validate their references against
     this bundle.
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
    errors += _check_no_existing_dois(df, context)
    errors += _check_duplicate_dois_in_bundle(df)
    _forward_campaign_sensor_set(df, context)
    _forward_doi_set(df, context)
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
                "message": f"({row['campaign_name']!r}, {row['sensor_name']!r}) already exists in database",
            })
    return errors


def _check_no_existing_dois(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """doi must not already exist in the production doi table. Blank doi is allowed (skipped)."""
    if "doi" not in df.columns:
        return []
    non_blank = df[df["doi"].notna() & (df["doi"].astype(str).str.strip() != "")]
    deduped = non_blank.drop_duplicates("doi")
    return check_not_in_db(
        deduped, "doi", context.db["doi_set"], "campaign_metadata"
    )


def _check_duplicate_dois_in_bundle(df: pd.DataFrame) -> list[dict]:
    """
    doi is a global primary key in production (not scoped to campaign), so a
    doi value repeated under a different campaign_name/sensor_name would slip
    past the mechanical pk_cols=[campaign_name, sensor_name, doi] check.
    Flag any non-blank doi that appears more than once anywhere in the bundle.
    """
    if "doi" not in df.columns:
        return []
    non_blank = df[df["doi"].notna() & (df["doi"].astype(str).str.strip() != "")]
    dupes = non_blank[non_blank.duplicated(subset="doi", keep=False)]
    if dupes.empty:
        return []
    errors = []
    for doi_val, group in dupes.groupby("doi"):
        rows = ", ".join(str(idx + 2) for idx in group.index)
        errors.append({
            "file": "campaign_metadata", "row": None, "column": "doi",
            "message": f"doi '{doi_val}' appears more than once in this bundle (rows: {rows})",
        })
    return errors


# ── Forwarded output ───────────────────────────────────────────────────────────

def _forward_campaign_sensor_set(df: pd.DataFrame, context: CheckContext) -> None:
    """
    Write the set of (campaign_name, sensor_name) tuples from this bundle
    into context so wavelengths.py and granule.py can validate FK references.
    """
    context.output["campaign_sensor_set"] = set(zip(df["campaign_name"], df["sensor_name"]))


def _forward_doi_set(df: pd.DataFrame, context: CheckContext) -> None:
    """
    Write the set of non-blank doi values from this bundle into context so
    traits.py can validate its optional doi FK against bundle-or-database.
    """
    if "doi" not in df.columns:
        context.output["doi_set"] = set()
        return
    non_blank = df["doi"][df["doi"].notna() & (df["doi"].astype(str).str.strip() != "")]
    context.output["doi_set"] = set(non_blank)
