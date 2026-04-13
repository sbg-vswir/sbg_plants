"""
QAQC checks for traits.csv

Checks (in order):
  1. Mechanical — required columns, no missing values, enum values,
                  no duplicate (plot_name, campaign_name, collection_date,
                  sample_name, trait), castable types.
                  Driven by checks/config/traits.json.
  2. Plot FK — each (campaign_name, plot_name) must resolve to this bundle
               or the production database.
  3. Conditional field — error_type is required whenever error is set.
  4. No existing insitu_plot_event — (campaign_name, plot_name, collection_date)
                                     must not already exist in production.
  5. No existing sample — (campaign_name, plot_name, collection_date, sample_name)
                          must not already exist in production.
  6. No existing leaf_trait — (campaign_name, plot_name, collection_date,
                               sample_name, trait) must not already exist in production.

  Checks 4–6 emit one error dict per violating row with a consistent message
  so the frontend's compressErrors() groups them into a bold 'Rows X-Y' summary.
"""

from __future__ import annotations

import pandas as pd

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import (
    load_config, run_mechanical_checks, check_foreign_key,
)

CONFIG = load_config("traits")
CONFIG["_file_name"] = "traits"


def check(context: CheckContext) -> CheckResult:
    df     = context.data["traits"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    errors += _check_plot_fk(df, context)
    errors += _check_error_type_conditional(df)
    errors += _check_no_existing_plot_events(df, context)
    errors += _check_no_existing_samples(df, context)
    errors += _check_no_existing_leaf_traits(df, context)
    return CheckResult("traits", len(df), errors, warnings)


# ── Custom checks ──────────────────────────────────────────────────────────────

def _check_plot_fk(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """Each (campaign_name, plot_name) must exist in this bundle or the DB."""
    all_plots = (
        set(context.output.get("plot_id_map", {}).keys())
        | context.db["plot_set"]
    )
    return check_foreign_key(
        df, ["campaign_name", "plot_name"], all_plots, "traits", column="plot_name"
    )


def _check_error_type_conditional(df: pd.DataFrame) -> list[dict]:
    """error_type is required whenever the error column contains a value."""
    errors = []
    for idx, row in df.iterrows():
        error_val  = row.get("error")
        error_type = row.get("error_type")
        if (pd.notna(error_val) and str(error_val).strip() != ""
                and (pd.isna(error_type) or str(error_type).strip() == "")):
            errors.append({
                "file": "traits", "row": int(idx + 2), "column": "error_type",
                "message": "error_type is required when error is set",
            })
    return errors


def _check_no_existing_plot_events(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """
    (campaign_name, plot_name, collection_date) must not already exist in
    production insitu_plot_event. One error per violating row with a consistent
    message so the frontend groups them into a bold Rows X-Y summary.
    """
    db_set = context.db["insitu_plot_event_set"]
    seen   = set()
    errors = []
    for idx, row in df.iterrows():
        key = (row["campaign_name"], row["plot_name"], str(row["collection_date"]).strip())
        if key in seen:
            continue
        seen.add(key)
        if key in db_set:
            errors.append({
                "file": "traits", "row": int(idx + 2), "column": None,
                "message": "insitu_plot_event already exists in database",
            })
    return errors


def _check_no_existing_samples(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """
    (campaign_name, plot_name, collection_date, sample_name) must not already
    exist in production sample.
    """
    db_set = context.db["sample_set"]
    seen   = set()
    errors = []
    for idx, row in df.iterrows():
        key = (
            row["campaign_name"], row["plot_name"],
            str(row["collection_date"]).strip(), row["sample_name"],
        )
        if key in seen:
            continue
        seen.add(key)
        if key in db_set:
            errors.append({
                "file": "traits", "row": int(idx + 2), "column": None,
                "message": "sample already exists in database",
            })
    return errors


def _check_no_existing_leaf_traits(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """
    (campaign_name, plot_name, collection_date, sample_name, trait) must not
    already exist in production leaf_traits.
    """
    db_set = context.db["leaf_trait_set"]
    errors = []
    for idx, row in df.iterrows():
        key = (
            row["campaign_name"], row["plot_name"],
            str(row["collection_date"]).strip(), row["sample_name"],
            str(row["trait"]),
        )
        if key in db_set:
            errors.append({
                "file": "traits", "row": int(idx + 2), "column": None,
                "message": "leaf_trait already exists in database",
            })
    return errors
