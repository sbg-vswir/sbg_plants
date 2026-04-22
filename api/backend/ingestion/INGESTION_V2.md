# Ingestion V2 — Implementation Brief

This document captures everything a fresh agent needs to implement the next phase of the
ingestion QAQC pipeline. Read `INGESTION.md` first for the full background on the existing
pipeline — this document only describes what needs to change or be added.

---

## Context: What We Discovered

Running `SELECT COUNT(*)` queries on the production database revealed several useful data
quality signals that are not currently checked during QAQC:

```sql
-- Raw table counts
SELECT COUNT(*) FROM vswir_plants.granule;        -- 102
SELECT COUNT(*) FROM vswir_plants.leaf_traits;     -- 1008
SELECT COUNT(*) FROM vswir_plants.sample;          -- 1262
SELECT COUNT(*) FROM vswir_plants.pixel;           -- 15236
SELECT COUNT(*) FROM vswir_plants.plot;            -- 477

-- View counts
SELECT COUNT(*) FROM vswir_plants.trait_view;                          -- 2001
SELECT COUNT(*) FROM vswir_plants.granule_view;                        -- 102
SELECT COUNT(*) FROM vswir_plants.plot_shape_view;                     -- 459
SELECT COUNT(*) FROM vswir_plants.trait_view WHERE trait IS NOT NULL;  -- 1008

-- Granules with no pixels (exist but never overlapped a plot)
SELECT COUNT(*) FROM vswir_plants.granule g
WHERE NOT EXISTS (
    SELECT 1 FROM vswir_plants.pixel px WHERE px.granule_id = g.granule_id
);
-- 41

-- Those 41 granules broken down — reveals bad epoch date
SELECT sensor_name, campaign_name, acquisition_date, COUNT(*)
FROM vswir_plants.granule g
WHERE NOT EXISTS (
    SELECT 1 FROM vswir_plants.pixel px WHERE px.granule_id = g.granule_id
)
GROUP BY sensor_name, campaign_name, acquisition_date
ORDER BY campaign_name, acquisition_date;
-- NEON AIS 1 | East River 2018 | 1970-01-01 | 41

-- Samples with no trait measurements
SELECT COUNT(*) FROM vswir_plants.sample s
WHERE NOT EXISTS (
    SELECT 1 FROM vswir_plants.leaf_traits lt
    WHERE lt.sample_name = s.sample_name
    AND lt.plot_id = s.plot_id
    AND lt.collection_date = s.collection_date
);
-- 993

-- Trait count distribution per sample
SELECT trait_count, COUNT(*) AS num_samples
FROM (
    SELECT s.sample_name, COUNT(lt.trait) AS trait_count
    FROM vswir_plants.sample s
    LEFT JOIN vswir_plants.leaf_traits lt
        ON lt.sample_name = s.sample_name
        AND lt.plot_id = s.plot_id
        AND lt.collection_date = s.collection_date
    GROUP BY s.sample_name
) sub
GROUP BY trait_count ORDER BY trait_count;
-- 0 traits: 993 samples
-- 2 traits:  33 samples
-- 3 traits:   2 samples
-- 4 traits: 234 samples

-- Granules grouped by campaign + sensor
SELECT campaign_name, sensor_name, COUNT(*)
FROM vswir_plants.granule
GROUP BY campaign_name, sensor_name
ORDER BY campaign_name, sensor_name;
-- East River 2018 | NEON AIS 1 | 102
```

### Key findings

1. **41 of 102 granules have no pixels** — they have bad `acquisition_date = 1970-01-01`
   (Unix epoch zero from a bad ingest). These will be fixed in a future data correction.
   The QAQC pipeline should warn on epoch dates so this is caught at ingest time going
   forward.

2. **993 of 1262 samples have no trait measurements** — samples exist in the `sample` table
   with no corresponding rows in `leaf_traits`. This is expected for some samples (collected
   but not yet measured) but the count per bundle should be surfaced as a warning.

3. **Trait count varies per sample** — most samples have 4 traits, some have 2 or 3. Any
   sample with fewer traits than the bundle's mode should produce a warning.

4. **Plots with no granule coverage** — plots that exist in traits but have no matching
   granule in the same bundle mean we have field data but no imagery for those locations.

---

## What Needs To Be Built

### Summary

Add a new `checks/cross_file.py` check module that runs **last** in the check pipeline.
It operates purely on the incoming DataFrames already in `context.data` — no DB queries,
no new dependencies. It surfaces data quality warnings that only make sense when looking
across multiple files simultaneously.

Additionally, add targeted warnings to the **existing per-file check modules** for issues
that are detectable within a single file.

None of the new checks should be **blocking errors** (`errors` list) — they are all
**warnings** only. The intent is to surface data quality signals in the QAQC report without
blocking ingestion of legitimate data.

---

## 1. New File: `qaqc/app/checks/cross_file.py`

This module is the main deliverable. It runs last in the check pipeline and has access to
all bundle DataFrames via `context.data` and all forwarded sets via `context.output`.

### Register it in `runner.py`

```python
# runner.py — add import and append to CHECKS list
from app.checks import campaign, wavelengths, granule, plots, traits, spectra, cross_file

CHECKS = [
    campaign,
    wavelengths,
    granule,
    plots,
    traits,
    spectra,
    cross_file,   # ← add at end
]
```

### `check(context)` function signature

```python
def check(context: CheckContext) -> CheckResult:
    """
    Cross-file data quality checks (warnings only, never blocking errors).

    Checks (in order):
      1. Plots with no traits — plots in this bundle that have no rows in traits.csv
      2. Traits with no granule coverage — trait plot_names that have no matching
         granule in granule_metadata.csv (field data with no imagery)
      3. Sample trait count distribution — warn on samples with fewer traits than
         the bundle mode
      4. Samples with no trait measurements — samples in traits.csv where trait is
         blank/null for all rows with that sample_name
    """
```

### Check 1: Plots with no traits

```python
def _check_plots_with_no_traits(context: CheckContext) -> list[dict]:
    """
    Warn for each plot in plots.geojson that has no rows in traits.csv.

    Uses:
        context.data["plots"]   — GeoJSON FeatureCollection dict
        context.data["traits"]  — DataFrame with columns: plot_name, campaign_name
    """
```

Logic:
- Extract `(campaign_name, plot_name)` from every GeoJSON feature's `properties`
- Extract unique `(campaign_name, plot_name)` from `df_traits`
- Warn for each plot that appears in the GeoJSON but not in traits

Warning shape:
```python
{
    "file": "cross_file",
    "row": None,
    "column": "plot_name",
    "message": f"Plot '{plot_name}' (campaign '{campaign_name}') has no trait measurements in traits.csv",
}
```

### Check 2: Traits with no granule coverage

```python
def _check_traits_with_no_granule_coverage(context: CheckContext) -> list[dict]:
    """
    Warn for each (campaign_name, plot_name) in traits.csv that has no corresponding
    granule in granule_metadata.csv and no plot-granule intersection in plots.geojson.

    Field data with no imagery. These plots cannot contribute to spectra extraction.

    Uses:
        context.data["traits"]          — DataFrame: plot_name, campaign_name
        context.data["plots"]           — GeoJSON: properties.plot_name, properties.campaign_name
    """
```

Logic:
- Build set of `(campaign_name, plot_name)` from plots.geojson features
- For each unique `(campaign_name, plot_name)` in traits that is NOT in plots set → warn
- Deduplicate — one warning per `(campaign_name, plot_name)` pair, not one per trait row

### Check 3: Sample trait count distribution

```python
def _check_sample_trait_count_distribution(context: CheckContext) -> list[dict]:
    """
    Compute the mode number of traits per sample across the bundle. Warn for any
    sample that has fewer traits than the mode.

    Example: if most samples have 4 traits, warn on samples with 1, 2, or 3.

    Uses:
        context.data["traits"]  — DataFrame: sample_name, plot_name, campaign_name,
                                             collection_date, trait
    """
```

Logic:
- Group `df_traits` by `(campaign_name, plot_name, collection_date, sample_name)`
- Count non-blank `trait` values per group
- Compute mode of those counts (use `pd.Series.mode()[0]`)
- Warn for each sample whose count < mode
- Include the sample's count and the bundle mode in the message

Warning shape:
```python
{
    "file": "cross_file",
    "row": None,
    "column": "trait",
    "message": (
        f"Sample '{sample_name}' (plot '{plot_name}', date '{collection_date}') "
        f"has {n} trait(s) but bundle mode is {mode}. "
        f"Expected columns may be missing or blank."
    ),
}
```

### Check 4: Samples with no trait measurements

```python
def _check_samples_with_no_traits(context: CheckContext) -> list[dict]:
    """
    Warn for each unique (campaign_name, plot_name, collection_date, sample_name)
    group in traits.csv where ALL rows have a blank/null trait value.

    These samples were collected but have no measurements in this bundle.

    Uses:
        context.data["traits"]  — DataFrame: sample_name, plot_name, campaign_name,
                                             collection_date, trait
    """
```

Logic:
- Group by `(campaign_name, plot_name, collection_date, sample_name)`
- A group has "no traits" if `trait` is blank/null for every row in the group
- Warn once per such group
- Include a summary warning at the end: `"N of M samples in this bundle have no trait measurements"`

---

## 2. Additions to Existing Check Modules

### `checks/granule.py` — add epoch date warning

Add a new private function and call it from `check()`:

```python
def check(context: CheckContext) -> CheckResult:
    df = context.data["granule_metadata"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    errors   += _check_campaign_sensor_fk(df, context)
    errors   += _check_no_existing_granule_ids(df, context)
    warnings += _check_epoch_acquisition_date(df)   # ← add
    _forward_granule_id_set(df, context)
    return CheckResult("granule_metadata", len(df), errors, warnings)


def _check_epoch_acquisition_date(df: pd.DataFrame) -> list[dict]:
    """
    Warn if any granule has acquisition_date of 1970-01-01 (Unix epoch zero).
    This indicates the date was never set and will result in the granule having
    no pixels after spatial intersection.

    Also warn for any acquisition_date that is before 2000-01-01, which almost
    certainly indicates a bad date regardless of exact value.
    """
```

Logic:
- Try to parse `acquisition_date` as a date (skip rows that fail — type check already handles that)
- Warn for any row where the parsed date is `1970-01-01` specifically — with the message
  "acquisition_date is 1970-01-01 (Unix epoch zero). This granule will have no pixels after
  spatial intersection. The date was likely not set during ingest."
- Also warn for any row where the parsed date is before `2000-01-01` with a more general
  "acquisition_date {value} appears implausibly early for airborne remote sensing data"

Warning shape:
```python
{
    "file": "granule_metadata",
    "row": idx + 2,
    "column": "acquisition_date",
    "message": "...",
}
```

---

## 3. `cross_file.py` Full Structure

```python
"""
Cross-file data quality checks.

All checks in this module produce warnings only — nothing here blocks ingestion.
These checks require data from multiple bundle files simultaneously and therefore
live in their own module, running last in the check pipeline.

Checks (in order):
  1. Plots with no traits
  2. Traits with no granule coverage
  3. Sample trait count distribution (warn on samples below bundle mode)
  4. Samples with no trait measurements
"""

from __future__ import annotations

import pandas as pd

from app.checks.types import CheckContext, CheckResult


def check(context: CheckContext) -> CheckResult:
    df_traits = context.data["traits"]
    geojson   = context.data["plots"]

    warnings = []
    warnings += _check_plots_with_no_traits(geojson, df_traits)
    warnings += _check_traits_with_no_granule_coverage(geojson, df_traits)
    warnings += _check_sample_trait_count_distribution(df_traits)
    warnings += _check_samples_with_no_traits(df_traits)

    # row_count = total trait rows checked
    return CheckResult("cross_file", len(df_traits), [], warnings)


def _check_plots_with_no_traits(geojson: dict, df_traits: pd.DataFrame) -> list[dict]:
    ...


def _check_traits_with_no_granule_coverage(geojson: dict, df_traits: pd.DataFrame) -> list[dict]:
    ...


def _check_sample_trait_count_distribution(df_traits: pd.DataFrame) -> list[dict]:
    ...


def _check_samples_with_no_traits(df_traits: pd.DataFrame) -> list[dict]:
    ...
```

---

## 4. Data Available in `context.data`

All DataFrames are `dtype=str` with blanks as `""` (parsed by `s3_files.parse_files()`).
The agent implementing this should treat blank and null as equivalent empty values.

| Key | Type | Relevant columns |
|-----|------|-----------------|
| `"traits"` | `pd.DataFrame` | `campaign_name`, `plot_name`, `collection_date`, `sample_name`, `trait`, `value` |
| `"granule_metadata"` | `pd.DataFrame` | `granule_id`, `campaign_name`, `sensor_name`, `acquisition_date` |
| `"plots"` | `dict` (GeoJSON) | `features[*].properties.plot_name`, `.campaign_name`, `.granule_id` |
| `"campaign_metadata"` | `pd.DataFrame` | `campaign_name`, `sensor_name` |
| `"wavelengths"` | `pd.DataFrame` | `campaign_name`, `sensor_name`, `band`, `wavelength` |
| `"spectra"` | `pd.DataFrame` | `campaign_name`, `plot_name`, `granule_id`, `glt_row`, `glt_column` |

---

## 5. What the QAQC Report Will Look Like After This Change

The full S3 report (`qaqc_report.json`) will gain a new top-level key `"cross_file"`:

```json
{
  "campaign_metadata": { "row_count": 1, "errors": [], "warnings": [] },
  "wavelengths":        { "row_count": 432, "errors": [], "warnings": [] },
  "granule_metadata":   { "row_count": 61, "errors": [],
                          "warnings": [
                            { "file": "granule_metadata", "row": 3, "column": "acquisition_date",
                              "message": "acquisition_date is 1970-01-01 (Unix epoch zero)..." }
                          ]},
  "plots":              { "row_count": 459, "errors": [], "warnings": [] },
  "traits":             { "row_count": 2001, "errors": [], "warnings": [] },
  "spectra":            { "row_count": 15236, "errors": [], "warnings": [] },
  "cross_file": {
    "row_count": 2001,
    "errors": [],
    "warnings": [
      { "file": "cross_file", "row": null, "column": "plot_name",
        "message": "Plot 'PLOT_042' (campaign 'East River 2018') has no trait measurements in traits.csv" },
      { "file": "cross_file", "row": null, "column": "trait",
        "message": "Sample 'S001' (plot 'PLOT_001', date '2018-07-15') has 2 trait(s) but bundle mode is 4. Expected columns may be missing or blank." },
      { "file": "cross_file", "row": null, "column": "trait",
        "message": "993 of 1262 samples in this bundle have no trait measurements." }
    ]
  }
}
```

The DynamoDB lightweight summary will also include the new key:
```json
"cross_file": { "passed": true, "row_count": 2001 }
```
Note: `"passed": true` because cross-file produces warnings only, never errors.

---

## 6. Files to Create / Modify

| Action | File |
|--------|------|
| **Create** | `qaqc/app/checks/cross_file.py` |
| **Modify** | `qaqc/app/checks/granule.py` — add `_check_epoch_acquisition_date` |
| **Modify** | `qaqc/app/checks/runner.py` — import and append `cross_file` to `CHECKS` |

No other files need to change. No new dependencies. No DB queries.

---

## 7. Testing

There is no test suite currently. The implementer should verify by:

1. Constructing a minimal `CheckContext` with synthetic DataFrames that trigger each warning
   condition and asserting the expected warning messages are present in the returned
   `CheckResult.warnings` list.
2. Constructing a "clean" context with no issues and asserting `warnings == []`.

Each check function is pure (no side effects, no DB calls) so unit testing is straightforward.

---

## Notes

- The `cross_file` module name follows the same convention as other check modules.
- `runner.py` uses the module's `__name__` for logging — the log line will read
  `"Running check: cross_file"`.
- The `has_errors` flag in `runner.run_all()` only flips to `True` when `result.errors`
  is non-empty. Since cross-file produces only warnings, it will never cause a `QAQC_FAIL`.
- If `context.data["traits"]` is empty (e.g. a bundle with no traits file), checks 3 and 4
  should return `[]` gracefully — guard with `if df_traits.empty: return []`.
- If `context.data["plots"]` has no features, check 1 should return `[]` gracefully.
