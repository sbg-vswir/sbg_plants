"""
QAQC checks for wavelengths.csv

Checks (in order):
  1. Mechanical — required columns, no missing values, no duplicate
                  (campaign_name, sensor_name, band), castable types.
                  Driven by checks/config/wavelengths.json.
  2. FK — each (campaign_name, sensor_name) must resolve to this bundle
          or the production database.
  3. No existing (campaign_name, sensor_name) — must not already exist in
                                                 production sensor_campaign.
  4. Band contiguity — per sensor, band values must be 0-based contiguous
                       integers (0, 1, 2, … N-1).
  5. Wavelength monotonicity — per sensor, wavelength must increase
                                strictly with band index.
  6. Wavelength range — all wavelength values must fall within the plausible
                        VSWIR range (350–2600 nm).
  7. FWHM range — all fwhm values must be within 0.1–100 nm.
"""

from __future__ import annotations

import pandas as pd

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import load_config, run_mechanical_checks

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
    errors += _check_campaign_sensor_fk(df, context)
    errors += _check_no_existing_sensor_campaigns(df, context)
    errors += _check_band_contiguity(df)
    errors += _check_wavelength_monotonicity(df)
    errors += _check_wavelength_range(df)
    errors += _check_fwhm_range(df)
    return CheckResult("wavelengths", len(df), errors, warnings)


# ── Custom checks ──────────────────────────────────────────────────────────────

def _check_campaign_sensor_fk(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """Each (campaign_name, sensor_name) pair must exist in this bundle or the DB."""
    all_sensors = (
        context.output.get("campaign_sensor_set", set())
        | context.db["campaign_sensor_set"]
    )
    errors = []
    for (camp, sens), _ in df.groupby(["campaign_name", "sensor_name"]):
        if (camp, sens) not in all_sensors:
            errors.append({
                "file": "wavelengths", "row": None, "column": None,
                "message": (
                    f"(campaign_name='{camp}', sensor_name='{sens}') "
                    f"not found in campaign_metadata or database"
                ),
            })
    return errors


def _check_no_existing_sensor_campaigns(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """
    (campaign_name, sensor_name) must not already exist in production sensor_campaign.
    Reported once per sensor group (not per band row).
    """
    errors = []
    for (camp, sens), grp in df.groupby(["campaign_name", "sensor_name"]):
        if (camp, sens) in context.db["campaign_sensor_set"]:
            # Use the first row number of the group as the representative row
            first_row = grp.index[0] + 2
            errors.append({
                "file": "wavelengths", "row": int(first_row), "column": None,
                "message": "sensor_campaign already exists in database",
            })
    return errors


def _check_band_contiguity(df: pd.DataFrame) -> list[dict]:
    """
    Per (campaign, sensor), band values must be 0-based contiguous integers.
    e.g. [0, 1, 2, 3] is valid; [0, 2, 3] or [1, 2, 3] are not.
    """
    errors = []
    for (camp, sens), grp in df.groupby(["campaign_name", "sensor_name"]):
        try:
            bands = sorted(int(b) for b in grp["band"])
        except (ValueError, TypeError):
            continue  # non-castable values already caught by the type check
        if bands != list(range(len(bands))):
            errors.append({
                "file": "wavelengths", "row": None, "column": "band",
                "message": (
                    f"band indices for ({camp}, {sens}) are not "
                    f"0-based contiguous integers"
                ),
            })
    return errors


def _check_wavelength_monotonicity(df: pd.DataFrame) -> list[dict]:
    """
    Per (campaign, sensor), wavelength values must increase monotonically
    with band index. Band column is cast to int before sorting to avoid
    lexicographic ordering of string values (e.g. "10" < "2" as strings).
    """
    errors = []
    for (camp, sens), grp in df.groupby(["campaign_name", "sensor_name"]):
        try:
            wl = (
                grp.assign(_band_int=grp["band"].astype(int))
                .sort_values("_band_int")["wavelength"]
                .astype(float)
                .tolist()
            )
        except (ValueError, TypeError):
            continue  # non-castable values already caught by the type check
        if wl != sorted(wl):
            errors.append({
                "file": "wavelengths", "row": None, "column": "wavelength",
                "message": (
                    f"wavelength values for ({camp}, {sens}) "
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
