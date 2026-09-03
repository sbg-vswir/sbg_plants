"""
QAQC checks for traits.csv

Checks (in order):
  1. Mechanical — required columns, no missing values, enum values,
                  castable types. Driven by checks/config/traits.json.
                  Duplicate-row detection is NOT config-driven for this file
                  (pk_cols is intentionally empty) — see _check_duplicate_rows.
  2. Plot FK — each (campaign_name, plot_name) must resolve to this bundle
               or the production database.
  3. Conditional field — error_type is required whenever error is set.
  4. No existing insitu_plot_event — (campaign_name, plot_name, collection_date)
                                     must not already exist in production.
  5. No existing sample — (campaign_name, plot_name, collection_date, sample_name)
                          must not already exist in production.
  6. No existing leaf_trait — (campaign_name, plot_name, collection_date,
                               sample_name, trait) must not already exist in production.
  7. DOI FK — each non-blank doi must resolve to the production doi table or
              to a doi submitted in this same bundle's campaign_metadata.csv.
  8. Duplicate rows — (sample_name, plot_name, collection_date, trait, method,
                       handling, units) must be unique within the bundle.
                       A single leaf_traits row has no natural-key uniqueness
                       constraint in the DB (trait_id is a surrogate serial —
                       the same trait CAN be recorded via a different
                       method/handling/units), so this within-batch check is
                       the only guard against submitting the exact same
                       measurement twice. Sample-only rows (blank trait
                       fields) collapse to the same key when repeated for the
                       same sample and are still flagged — a sample must not
                       be declared more than once.

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

_DUP_KEY_COLS = ["sample_name", "plot_name", "collection_date", "trait", "method", "handling", "units"]


def check(context: CheckContext) -> CheckResult:
    df     = context.data["traits"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    errors += _check_plot_fk(df, context)
    errors += _check_error_type_conditional(df)
    errors += _check_no_existing_plot_events(df, context)
    errors += _check_no_existing_samples(df, context)
    errors += _check_no_existing_leaf_traits(df, context)
    errors += _check_trait_fields(df)
    errors += _check_doi_fk(df, context)
    errors += _check_duplicate_rows(df)
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

    Rows with no trait data are sample-only rows and are skipped.
    """
    db_set = context.db["leaf_trait_set"]
    errors = []

    for idx, row in df.iterrows():
        if pd.isna(row["trait"]) or str(row["trait"]).strip() == "":
            continue

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

def _check_trait_fields(df: pd.DataFrame) -> list[dict]:
    """Trait fields must either all be populated or all be blank."""
    trait_cols = ["trait", "value", "method", "handling", "units"]
    errors = []

    for idx, row in df.iterrows():
        populated = [
            col for col in trait_cols
            if pd.notna(row[col]) and str(row[col]).strip() != ""
        ]

        if populated and len(populated) != len(trait_cols):
            missing = [
                col for col in trait_cols
                if pd.isna(row[col]) or str(row[col]).strip() == ""
            ]

            errors.append({
                "file": "traits",
                "row": int(idx + 2),
                "column": missing[0],
                "message": (
                    "trait fields must either all be populated or all be blank; "
                    f"missing: {', '.join(missing)}"
                ),
            })

    return errors


def _check_doi_fk(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """
    Each non-blank doi must resolve to the production doi table or to a doi
    submitted in this same bundle's campaign_metadata.csv. Blank doi is
    allowed — not every trait row is tied to a specific DOI.
    """
    if "doi" not in df.columns:
        return []

    valid_dois = context.db["doi_set"] | context.output.get("doi_set", set())
    errors = []
    for idx, row in df.iterrows():
        doi_val = row.get("doi")
        if pd.isna(doi_val) or str(doi_val).strip() == "":
            continue
        if doi_val not in valid_dois:
            errors.append({
                "file": "traits", "row": int(idx + 2), "column": "doi",
                "message": f"doi '{doi_val}' not found in bundle campaign_metadata.csv or database",
            })
    return errors


def _check_duplicate_rows(df: pd.DataFrame) -> list[dict]:
    """
    (sample_name, plot_name, collection_date, trait, method, handling, units)
    must be unique within the bundle.

    This deliberately covers two distinct situations with one rule:
      - Real trait measurements: the same trait recorded via a different
        method/handling/units is NOT a duplicate (leaf_traits.trait_id is a
        surrogate serial — there's no DB constraint stopping this, so this
        check is the only guard against submitting the exact same
        measurement twice).
      - Sample-only rows (trait/method/handling/units all blank): these
        collapse to the same key whenever the same sample repeats, and are
        still flagged — a sample must not be declared more than once.

    Emits a distinct, more actionable message depending on which case a
    duplicate group falls into.
    """
    missing = [c for c in _DUP_KEY_COLS if c not in df.columns]
    if missing:
        return []

    dupe_mask = df.duplicated(subset=_DUP_KEY_COLS, keep=False)
    if not dupe_mask.any():
        return []

    errors = []
    for _, group in df[dupe_mask].groupby(_DUP_KEY_COLS, dropna=False, sort=False):
        rows = ", ".join(str(idx + 2) for idx in group.index)
        sample_name, plot_name, collection_date = (
            group.iloc[0]["sample_name"], group.iloc[0]["plot_name"], group.iloc[0]["collection_date"],
        )
        trait_val = group.iloc[0]["trait"]
        is_blank_trait = pd.isna(trait_val) or str(trait_val).strip() == ""

        if is_blank_trait:
            message = (
                f"sample '{sample_name}' in plot '{plot_name}' (date '{collection_date}') "
                f"is declared {len(group)} times with no trait data — remove the extra row(s) "
                f"(rows: {rows})"
            )
        else:
            method_val, handling_val, units_val = (
                group.iloc[0]["method"], group.iloc[0]["handling"], group.iloc[0]["units"],
            )
            message = (
                f"duplicate trait measurement for sample '{sample_name}' in plot '{plot_name}' "
                f"(date '{collection_date}'): trait='{trait_val}', method='{method_val}', "
                f"handling='{handling_val}', units='{units_val}' appears {len(group)} times "
                f"(rows: {rows})"
            )

        errors.append({
            "file": "traits", "row": None, "column": "trait" if not is_blank_trait else "sample_name",
            "message": message,
        })
    return errors

