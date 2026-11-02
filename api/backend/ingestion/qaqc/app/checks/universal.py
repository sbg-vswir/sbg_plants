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
    check_existing_identical(df, key_cols, compare_cols, db_rows, file_name, label)

── Value normalization (shared with db_refs so bundle and DB keys line up) ──
    normalize(val, typ)
    row_key(row, key_cols, required)
    values_match(bundle_val, prod_val, typ)
"""

from __future__ import annotations

import json
import math
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


_TIME_FORMATS = ("%H:%M:%S", "%H%M%S", "%H:%M", "%I:%M:%S %p")


def _is_blank(val) -> bool:
    """
    True if val is null, or an empty/whitespace-only string.

    Bundle CSVs are read with dtype=str and .fillna(""), so "missing" shows
    up as "" far more often than it shows up as a real NaN — pd.isna() alone
    misses that case, which is why check_castable was raising false
    "cannot be cast" errors on blank required-but-empty cells.
    """
    return pd.isna(val) or (isinstance(val, str) and val.strip() == "")


def _parse_time(val) -> None:
    """
    Raises ValueError if val doesn't match any known time format.
    Tries HH:MM:SS first, then the unseparated HHMMSS form seen in some
    instrument logs (e.g. "195050"), then a couple of other common variants.
    """
    s = str(val).strip()
    for fmt in _TIME_FORMATS:
        try:
            datetime.strptime(s, fmt)
            return
        except ValueError:
            continue
    raise ValueError(f"time '{s}' does not match any known format")


def check_castable(df: pd.DataFrame, type_cols: dict, file_name: str) -> list[dict]:
    """
    Each non-blank value in a typed column must be castable to its declared type.
    type_cols: { column_name: float | int | bool | "date" | "time" }

    Notes on tolerance, since these have all shown up in real bundles:
      - int accepts float-serialized strings like "142.0" (common when the
        source column round-tripped through a float dtype before CSV export).
      - float strips a trailing "%" before parsing.
      - time accepts unseparated "HHMMSS" in addition to "HH:MM:SS".
    """
    errors = []
    for col, typ in type_cols.items():
        if col not in df.columns:
            continue
        for idx, val in df[col].items():
            if _is_blank(val):
                continue
            try:
                if typ == float:
                    float(val)
                elif typ == int:
                    f = float(val)
                    if not f.is_integer():
                        raise ValueError(f"'{val}' is not a whole number")
                    int(f)
                elif typ == bool:
                    value = str(val).lower()
                    if value in ("true", "1", "yes", "1.0"):
                        df.at[idx, col] = True
                    elif value in ("false", "0", "no", "0.0"):
                        df.at[idx, col] = False
                    else:
                        raise ValueError
                elif typ == "date":
                    pd.to_datetime(str(val), dayfirst=False)
                elif typ == "time":
                    _parse_time(val)
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
            f"'{row[key_col]}' already exists in database",
            row=idx + 2,
            column=column or key_col,
        ))
    return errors


def check_existing_identical(
    df: pd.DataFrame,
    key_cols: dict[str, str],
    compare_cols: dict[str, str],
    db_rows: dict,
    file_name: str,
    label: str,
    required: list[str] | None = None,
) -> tuple[list[dict], list[dict], pd.Series]:
    """
    Reuse-if-identical rule for rows that may already be in production.

    key_cols / compare_cols: { column: type } — type is one of the normalize()
                             types. key_cols form the natural key.
    db_rows: { normalized key tuple: { column: value } } from db_refs.
    required: key columns that must be non-blank (default: all of them);
              the others are optional scopes where blank is part of the key.

    For each row whose key is already in production:
      - every compare column matches → the row is reused (not staged again)
      - any compare column differs   → one error per key naming the columns
    Rows with a blank required key part are skipped (the missing-value check
    reports them).

    Returns (errors, warnings, existing) — existing is a boolean Series on
    df.index, True for rows whose key is already in production. The staging
    load drops those rows.
    """
    errors   = []
    existing = pd.Series(False, index=df.index)
    if df.empty or not db_rows or any(c not in df.columns for c in key_cols):
        return errors, [], existing

    checked = set()
    for idx, row in df.iterrows():
        key = row_key(row, key_cols, required)
        if key is None or key not in db_rows:
            continue
        existing[idx] = True
        if key in checked:
            continue
        checked.add(key)
        prod  = db_rows[key]
        diffs = [
            c for c, typ in compare_cols.items()
            if c in df.columns and not values_match(row[c], prod.get(c), typ)
        ]
        if diffs:
            key_desc  = ", ".join(f"{c}='{row[c]}'" for c in key_cols)
            diff_desc = "; ".join(
                f"{c}: bundle '{row[c]}' vs production '{prod.get(c)}'" for c in diffs
            )
            errors.append(_err(
                file_name,
                f"{label} ({key_desc}) already exists in production with different values — {diff_desc}",
                row=idx + 2,
            ))

    warnings = []
    if len(checked) and not errors:
        warnings.append(_err(
            file_name,
            f"{len(checked)} {label}(s) already in production with identical values — reused, not added again",
        ))
    return errors, warnings, existing


# ── Value normalization ────────────────────────────────────────────────────────

_BOOL_TRUE  = {"true", "t", "yes", "y", "1", "1.0"}
_BOOL_FALSE = {"false", "f", "no", "n", "0", "0.0"}


def normalize(val, typ: str = "str"):
    """
    Normalize a bundle (string) or DB value so the two compare equal.
    typ: str | lower | float | int | bool | date | floatlist | strlist.
    Blank → None. Unparseable values are returned as the stripped string
    (the type checks report those separately).
    """
    if typ in ("floatlist", "strlist"):
        if val is None or (not isinstance(val, (list, tuple)) and _is_blank(val)):
            return None
        items = val if isinstance(val, (list, tuple)) else str(val).split(";")
        items = [str(v).strip() for v in items if str(v).strip()]
        if typ == "strlist":
            return tuple(sorted(set(items))) or None
        return tuple(float(v) for v in items) or None
    if isinstance(val, (list, tuple)) or _is_blank(val):
        return None
    s = str(val).strip()
    try:
        if typ == "lower":
            return s.lower()
        if typ == "float":
            return float(s)
        if typ == "int":
            return int(float(s))
        if typ == "bool":
            if isinstance(val, bool):
                return val
            low = s.lower()
            return True if low in _BOOL_TRUE else False if low in _BOOL_FALSE else s
        if typ == "date":
            return pd.to_datetime(s).date().isoformat()
    except (ValueError, TypeError):
        return s
    return s


def row_key(row, key_cols: dict[str, str], required: list[str] | None = None) -> tuple | None:
    """
    Normalized key tuple for a row, or None if a required key part is blank.
    required defaults to every key column.
    """
    required = key_cols if required is None else required
    key = tuple(normalize(row.get(c), typ) for c, typ in key_cols.items())
    if any(k is None for c, k in zip(key_cols, key) if c in required):
        return None
    return key


def values_match(bundle_val, prod_val, typ: str) -> bool:
    """True if two values are equal after normalizing; floats within FLOAT4 precision."""
    a, b = normalize(bundle_val, typ), normalize(prod_val, typ)
    if typ == "floatlist" and a is not None and b is not None:
        return len(a) == len(b) and all(math.isclose(x, y, rel_tol=1e-6) for x, y in zip(a, b))
    if typ == "float" and isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-6)  # FLOAT4 keeps ~7 significant digits
    return a == b
