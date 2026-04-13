"""
Shared QAQC check functions and utilities.

Every function returns a list of error or warning dicts (empty list = pass):
    { "file": str, "row": int | None, "column": str | None, "message": str }

── Config loading ────────────────────────────────────────────────────────────
    load_config(file_name)

── Mechanical checks (driven by per-file JSON config) ───────────────────────
    run_mechanical_checks(df, enums, config)

── Individual structural checks ─────────────────────────────────────────────
    check_required_columns(df, required, file_name)
    check_no_missing_values(df, required, file_name)
    check_enum_values(df, enum_cols, enums, file_name)
    check_no_duplicates(df, pk_cols, file_name)
    check_castable(df, type_cols, file_name)
    check_extra_columns(df, known_cols, file_name)

── Cross-reference checks ────────────────────────────────────────────────────
    check_foreign_key(df, key_cols, reference_set, file_name, column)
    check_not_in_db(df, key_col, db_set, file_name, column)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── Config loading ─────────────────────────────────────────────────────────────

_CONFIG_DIR = Path(__file__).parent / "config"

_TYPE_MAP = {
    "float": float,
    "int":   int,
    "bool":  bool,
    "date":  "date",
    "time":  "time",
}


def load_config(file_name: str) -> dict:
    """
    Load the JSON check config for a bundle file.
    Returns the raw dict — keys: required_cols, nullable_cols, enum_cols,
    type_cols, pk_cols (plus any file-specific keys like required_props).
    """
    path = _CONFIG_DIR / f"{file_name}.json"
    with open(path) as fh:
        return json.load(fh)


# ── Mechanical checks ──────────────────────────────────────────────────────────

def run_mechanical_checks(
    df: pd.DataFrame,
    enums: dict,
    config: dict,
) -> tuple[list[dict], list[dict]]:
    """
    Run all config-driven checks for a CSV file in the standard order.
    Returns (errors, warnings).

    Stops early and returns immediately if required columns are missing,
    since all subsequent checks depend on those columns being present.
    """
    file_name = config.get("_file_name", "unknown")

    errors = check_required_columns(df, config.get("required_cols", []), file_name)
    if errors:
        return errors, []

    errors   = (
        check_no_missing_values(df, config.get("required_cols", []),  file_name)
        + check_enum_values(df, config.get("enum_cols", {}),          enums, file_name)
        + check_no_duplicates(df, config.get("pk_cols", []),          file_name)
        + check_castable(df, _resolve_types(config.get("type_cols", {})), file_name)
    )
    warnings = check_extra_columns(
        df,
        config.get("required_cols", []) + config.get("nullable_cols", []),
        file_name,
    )
    return errors, warnings


def _resolve_types(type_cols: dict) -> dict:
    """Map string type names from config JSON to the values check_castable() expects."""
    return {col: _TYPE_MAP[typ] for col, typ in type_cols.items() if typ in _TYPE_MAP}


# ── Structural checks ──────────────────────────────────────────────────────────

def _err(file_name: str, message: str, row=None, column=None) -> dict:
    return {"file": file_name, "row": int(row) if row is not None else None, "column": column, "message": message}


def check_required_columns(df: pd.DataFrame, required: list[str], file_name: str) -> list[dict]:
    """Every column in required must be present in the DataFrame."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        return [_err(file_name, f"missing required columns: {', '.join(missing)}")]
    return []


def check_no_missing_values(df: pd.DataFrame, required: list[str], file_name: str) -> list[dict]:
    """No null or blank values allowed in required columns."""
    errors = []
    for col in required:
        if col not in df.columns:
            continue
        blank_rows = df[df[col].isnull() | (df[col].astype(str).str.strip() == "")].index
        for r in blank_rows:
            errors.append(_err(file_name, f"missing value in column '{col}'", row=r + 2, column=col))
    return errors


def check_enum_values(
    df: pd.DataFrame,
    enum_cols: dict[str, str],
    enums: dict[str, set],
    file_name: str,
) -> list[dict]:
    """
    Each non-null value in an enum column must be a valid enum label.
    enum_cols: { column_name: enum_type_name }
    enums:     { enum_type_name: set(valid_labels) }  — loaded from DB at startup
    """
    errors = []
    for col, enum_type in enum_cols.items():
        if col not in df.columns:
            continue
        valid        = enums.get(enum_type, set())
        invalid_mask = ~df[col].isin(valid) & df[col].notna() & (df[col].astype(str).str.strip() != "")
        for idx, row in df[invalid_mask].iterrows():
            errors.append(_err(
                file_name,
                f"'{row[col]}' is not a valid value for '{col}' (valid: {sorted(valid)})",
                row=idx + 2,
                column=col,
            ))
    return errors


def check_no_duplicates(df: pd.DataFrame, pk_cols: list[str], file_name: str) -> list[dict]:
    """Composite primary key columns must not have duplicate combinations."""
    if not pk_cols:
        return []
    dupes = df[df.duplicated(subset=pk_cols, keep=False)]
    if dupes.empty:
        return []
    count = len(dupes) // 2
    return [_err(file_name, f"{count} duplicate row(s) found on columns: {', '.join(pk_cols)}")]


def check_castable(df: pd.DataFrame, type_cols: dict, file_name: str) -> list[dict]:
    """
    Each non-null value in a typed column must be castable to its declared type.
    type_cols: { column_name: float | int | bool | "date" | "time" }
    """
    errors = []
    for col, typ in type_cols.items():
        if col not in df.columns:
            continue
        for idx, val in df[col].items():
            if pd.isna(val):
                continue
            try:
                if typ == float:
                    float(val)
                elif typ == int:
                    int(val)
                elif typ == bool:
                    if str(val).lower() not in ("true", "false", "1", "0", "yes", "no"):
                        raise ValueError
                elif typ == "date":
                    pd.to_datetime(str(val), dayfirst=False)
                elif typ == "time":
                    datetime.strptime(str(val), "%H:%M:%S")
            except (ValueError, TypeError):
                errors.append(_err(
                    file_name,
                    f"'{val}' in column '{col}' cannot be cast to {typ}",
                    row=idx + 2,
                    column=col,
                ))
    return errors


def check_extra_columns(
    df: pd.DataFrame,
    known_cols: list[str],
    file_name: str,
) -> list[dict]:
    """Warn about columns present in the file that are not in the declared schema."""
    known = set(known_cols)
    extra = [c for c in df.columns if c not in known]
    if not extra:
        return []
    return [_err(file_name, f"unexpected column(s) not in schema and will not be ingested: {', '.join(sorted(extra))}")]


# ── Cross-reference checks ─────────────────────────────────────────────────────

def check_foreign_key(
    df: pd.DataFrame,
    key_cols: list[str],
    reference_set: set,
    file_name: str,
    column: str | None = None,
) -> list[dict]:
    """
    Each row's key tuple must exist in reference_set.

    key_cols:      list of column names that form the foreign key.
                   For a single-column FK pass ["col_name"].
    reference_set: combined bundle + DB set of valid key tuples.
                   For single-column FKs this is a set of plain values,
                   for multi-column FKs a set of tuples.
    column:        column name to report on error (optional, defaults to None).

    Example — check that (campaign_name, sensor_name) resolves:
        check_foreign_key(
            df, ["campaign_name", "sensor_name"],
            bundle_sensors | db_sensors,
            "granule_metadata",
        )
    """
    errors = []
    for idx, row in df.iterrows():
        key = tuple(row[c] for c in key_cols) if len(key_cols) > 1 else row[key_cols[0]]
        if key not in reference_set:
            cols_desc = ", ".join(f"{c}='{row[c]}'" for c in key_cols)
            errors.append(_err(
                file_name,
                f"({cols_desc}) not found in bundle or database",
                row=idx + 2,
                column=column,
            ))
    return errors


def check_not_in_db(
    df: pd.DataFrame,
    key_col: str,
    db_set: set,
    file_name: str,
    column: str | None = None,
) -> list[dict]:
    """
    Each row's value must NOT already exist in db_set (inverse FK check).
    Used to prevent re-ingesting data that is already in production.

    Returns one error dict per violating row so the frontend's compressErrors()
    can group them into a 'Rows X-Y: message (N rows)' summary with bold formatting.

    Example — granule_id must not already exist:
        check_not_in_db(df, "granule_id", db_granule_ids, "granule_metadata", "granule_id")
    """
    errors = []
    already_exists = df[df[key_col].isin(db_set)]
    for idx, row in already_exists.iterrows():
        errors.append(_err(
            file_name,
            f"{key_col} already exists in database",
            row=idx + 2,
            column=column or key_col,
        ))
    return errors
