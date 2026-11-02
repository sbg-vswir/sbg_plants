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
  4. Existing plot events / samples / leaf traits — rows already in production
     follow the reuse-if-identical rule (universal.check_existing_identical):
       insitu_plot_event  key (campaign_name, plot_name, collection_date)
       sample             key + sample_name
       leaf_traits        key + sample_name, trait, method, handling, units
                          (the production leaf_traits_unique key)
     Identical → reused (not staged again), different → error.
  5. Trait fields — trait, value, method, handling, units are all set or all blank.
  6. Duplicate rows — (sample_name, plot_name, collection_date, trait, method,
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
"""

from __future__ import annotations

import pandas as pd

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import (
    load_config, run_mechanical_checks, check_foreign_key, check_existing_identical,
)
from app.db_refs import PLOT_EVENT_KEY, SAMPLE_KEY, LEAF_TRAIT_KEY

CONFIG = load_config("traits")
CONFIG["_file_name"] = "traits"

_DUP_KEY_COLS = ["sample_name", "plot_name", "collection_date", "trait", "method", "handling", "units"]

PLOT_EVENT_COLS = {"plot_veg_type": "str", "subplot_cover_method": "str", "floristic_survey": "bool"}
SAMPLE_COLS     = {
    "taxa": "str", "veg_or_cover_type": "str", "phenophase": "str", "sample_fc_class": "str",
    "sample_fc_percent": "int", "plant_status": "str", "canopy_position": "str",
}
LEAF_TRAIT_COLS = {"value": "float", "error": "float", "error_type": "str"}


def check(context: CheckContext) -> CheckResult:
    df     = context.data["traits"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    if any("missing required columns" in e["message"] for e in errors):
        return CheckResult("traits", len(df), errors, warnings)
    for col in ["trait", "value", "method", "handling", "units", "error", "error_type"]:
        if col not in df.columns:
            df[col] = ""
    errors += _check_plot_fk(df, context)
    errors += _check_error_type_conditional(df)
    existing_errors, existing_warnings = _check_existing_rows(df, context)
    errors   += existing_errors
    warnings += existing_warnings
    errors += _check_trait_fields(df)
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


def _check_existing_rows(df: pd.DataFrame, context: CheckContext) -> tuple[list[dict], list[dict]]:
    """
    Reuse-if-identical for plot events, samples and leaf traits already in
    production. Forwards the per-row "already in production" masks as
    context.output["existing"][table] for the staging load.
    """
    has_trait = df["trait"].astype(str).str.strip() != ""
    checks = [
        ("insitu_plot_event", df,            PLOT_EVENT_KEY, PLOT_EVENT_COLS, "insitu_plot_event_rows", "plot event"),
        ("sample",            df,            SAMPLE_KEY,     SAMPLE_COLS,     "sample_rows",            "sample"),
        ("leaf_traits",       df[has_trait], LEAF_TRAIT_KEY, LEAF_TRAIT_COLS, "leaf_trait_rows",        "leaf trait"),
    ]
    errors, warnings = [], []
    existing_out = context.output.setdefault("existing", {})
    for table, rows, key_cols, compare_cols, db_name, label in checks:
        e, w, existing = check_existing_identical(
            rows, key_cols, compare_cols, context.db[db_name], "traits", label,
        )
        errors   += e
        warnings += w
        existing_out[table] = existing.reindex(df.index, fill_value=False)
    return errors, warnings


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

