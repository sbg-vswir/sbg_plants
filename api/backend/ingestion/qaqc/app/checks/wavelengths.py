"""
QAQC checks for wavelengths.csv

Checks (in order):
  One group of bands per sensor calibration (campaign_name, sensor_name,
  sensor_date).

  1. Mechanical — required columns, no missing values, no duplicate
                  (campaign_name, sensor_name, sensor_date, band), castable
                  types. Driven by checks/config/wavelengths.json.
  2. FK — each (campaign_name, sensor_name, sensor_date) must resolve to this
          bundle or the production database.
  3. Band contiguity — per calibration, band values must be 0-based contiguous
                       integers (0, 1, 2, … N-1).
  4. Wavelength monotonicity — per calibration, wavelength must increase
                                strictly with band index.
  5. Wavelength range — all wavelength values must fall within the plausible
                        VSWIR range (350–2600 nm).
  6. FWHM range — all fwhm values must be within 0.1–100 nm.
  7. Matches production — bands for a calibration already in production must
                          be identical to it (reuse-if-identical).
"""

from __future__ import annotations

import pandas as pd

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import load_config, run_mechanical_checks, row_key, values_match
from app.db_refs import SENSOR_CAMPAIGN_KEY

CONFIG = load_config("wavelengths")
CONFIG["_file_name"] = "wavelengths"

# Plausible VSWIR wavelength range in nanometres.
# Values outside this almost certainly indicate the wrong unit (µm) or bad data.
_WAVELENGTH_MIN_NM = 350
_WAVELENGTH_MAX_NM = 2600

# Plausible FWHM range in nanometres (same unit as wavelength).
# Typical VSWIR sensors have FWHM of 8–15 nm; 0.1–100 gives generous headroom
# for unusual sensors while still catching the µm/nm unit mistake (e.g. fwhm=0.01).
_FWHM_MIN_NM = 0.1
_FWHM_MAX_NM = 100


def check(context: CheckContext) -> CheckResult:
    df     = context.data["wavelengths"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    if any("missing required columns" in e["message"] for e in errors):
        return CheckResult("wavelengths", len(df), errors, warnings)
    errors += _check_campaign_sensor_fk(df, context)
    errors += _check_band_contiguity(df)
    errors += _check_wavelength_monotonicity(df)
    errors += _check_wavelength_range(df)
    errors += _check_fwhm_range(df)
    errors += _check_matches_production(df, context)
    return CheckResult("wavelengths", len(df), errors, warnings)


_GROUP_COLS = ["campaign_name", "sensor_name", "sensor_date"]


def band_arrays(grp: pd.DataFrame) -> tuple[list[float], list[float]]:
    """(wavelengths, fwhms) of one calibration, ordered by band. Used by main.py too."""
    grp_sorted = grp.assign(_band_int=grp["band"].astype(float).astype(int)).sort_values("_band_int")
    return grp_sorted["wavelength"].astype(float).tolist(), grp_sorted["fwhm"].astype(float).tolist()


# ── Custom checks ──────────────────────────────────────────────────────────────

def _check_campaign_sensor_fk(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """Each (campaign_name, sensor_name, sensor_date) must exist in this bundle or the DB."""
    all_sensors = (
        context.output.get("campaign_sensor_set", set())
        | context.db["campaign_sensor_set"]
    )
    errors = []
    for (camp, sens, date), grp in df.groupby(_GROUP_COLS):
        if row_key(grp.iloc[0], SENSOR_CAMPAIGN_KEY) not in all_sensors:
            errors.append({
                "file": "wavelengths", "row": None, "column": None,
                "message": (
                    f"(campaign_name='{camp}', sensor_name='{sens}', sensor_date='{date}') "
                    f"not found in campaign_metadata or database"
                ),
            })
    return errors


def _check_matches_production(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """Bands for a calibration already in production must match it exactly."""
    db_rows = context.db["sensor_campaign_rows"]
    errors  = []
    for (camp, sens, date), grp in df.groupby(_GROUP_COLS):
        prod = db_rows.get(row_key(grp.iloc[0], SENSOR_CAMPAIGN_KEY))
        if prod is None:
            continue
        try:
            wl, fwhm = band_arrays(grp)
        except (ValueError, TypeError):
            continue  # non-castable values already caught by the type check
        differing = [
            name for name, bundle_vals, prod_vals in (
                ("wavelength", wl, prod["wavelength_center"]), ("fwhm", fwhm, prod["fwhm"]),
            )
            if not values_match(bundle_vals, list(prod_vals), "floatlist")
        ]
        if differing:
            errors.append({
                "file": "wavelengths", "row": None, "column": differing[0],
                "message": (
                    f"(campaign_name='{camp}', sensor_name='{sens}', sensor_date='{date}') "
                    f"already exists in production with different {' and '.join(differing)} values "
                    f"— a new calibration needs a new sensor_date"
                ),
            })
    return errors


def _check_band_contiguity(df: pd.DataFrame) -> list[dict]:
    """
    Per calibration, band values must be 0-based contiguous integers.
    e.g. [0, 1, 2, 3] is valid; [0, 2, 3] or [1, 2, 3] are not.
    """
    errors = []
    for (camp, sens, date), grp in df.groupby(_GROUP_COLS):
        try:
            bands = sorted(int(float(b)) for b in grp["band"])
        except (ValueError, TypeError):
            continue  # non-castable values already caught by the type check
        if bands != list(range(len(bands))):
            errors.append({
                "file": "wavelengths", "row": None, "column": "band",
                "message": (
                    f"band indices for ({camp}, {sens}, {date}) are not "
                    f"0-based contiguous integers"
                ),
            })
    return errors


def _check_wavelength_monotonicity(df: pd.DataFrame) -> list[dict]:
    """
    Per calibration, wavelength values must increase monotonically
    with band index. Band column is cast to int before sorting to avoid
    lexicographic ordering of string values (e.g. "10" < "2" as strings).
    """
    errors = []
    for (camp, sens, date), grp in df.groupby(_GROUP_COLS):
        try:
            wl, _ = band_arrays(grp)
        except (ValueError, TypeError):
            continue  # non-castable values already caught by the type check
        if wl != sorted(wl):
            errors.append({
                "file": "wavelengths", "row": None, "column": "wavelength",
                "message": (
                    f"wavelength values for ({camp}, {sens}, {date}) "
                    f"are not monotonically increasing"
                ),
            })
    return errors


def _check_wavelength_range(df: pd.DataFrame) -> list[dict]:
    """
    All wavelength values must fall within the plausible VSWIR range
    ({min}–{max} nm). Values outside this range almost certainly indicate
    the wrong unit (µm instead of nm) or corrupted data.
    """.format(min=_WAVELENGTH_MIN_NM, max=_WAVELENGTH_MAX_NM)
    errors = []
    for idx, row in df.iterrows():
        try:
            wl = float(row["wavelength"])
        except (ValueError, TypeError):
            continue  # non-castable values already caught by the type check
        if not (_WAVELENGTH_MIN_NM <= wl <= _WAVELENGTH_MAX_NM):
            errors.append({
                "file": "wavelengths", "row": int(idx + 2), "column": "wavelength",
                "message": (
                    f"wavelength {wl} is outside the plausible VSWIR range "
                    f"({_WAVELENGTH_MIN_NM}–{_WAVELENGTH_MAX_NM} nm) — "
                    f"check that values are in nm, not µm"
                ),
            })
    return errors


def _check_fwhm_range(df: pd.DataFrame) -> list[dict]:
    """
    All fwhm values must be positive and within a plausible spectral bandwidth
    ({min}–{max} nm). Catches the µm/nm unit mistake (e.g. fwhm=0.01 when 10 nm
    was intended) and clearly erroneous values. FWHM is not checked for
    monotonicity — it commonly varies non-monotonically across a sensor's
    spectral range.
    """.format(min=_FWHM_MIN_NM, max=_FWHM_MAX_NM)
    errors = []
    for idx, row in df.iterrows():
        try:
            fwhm = float(row["fwhm"])
        except (ValueError, TypeError):
            continue  # non-castable values already caught by the type check
        if not (_FWHM_MIN_NM <= fwhm <= _FWHM_MAX_NM):
            errors.append({
                "file": "wavelengths", "row": int(idx + 2), "column": "fwhm",
                "message": (
                    f"fwhm {fwhm} is outside the plausible range "
                    f"({_FWHM_MIN_NM}–{_FWHM_MAX_NM} nm) — "
                    f"check that values are in nm, not µm"
                ),
            })
    return errors
