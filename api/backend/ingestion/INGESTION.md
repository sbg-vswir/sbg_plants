# Ingestion Pipeline

## Overview

Data is submitted as a bundle of 6 files. Files are validated asynchronously against the
production database, loaded into a staging schema on success, and promoted to production
after admin review and approval. If validation fails, individual files can be replaced and
re-checked without starting over.

| File | Tables |
|------|--------|
| `campaign_metadata.csv` | `campaign`, `sensor_campaign` |
| `wavelengths.csv` | `sensor_campaign` (`wavelength_center`, `fwhm`) |
| `granule_metadata.csv` | `granule` |
| `plots.geojson` | `plot_shape`, `plot`, `plot_raster_intersect` |
| `traits.csv` | `insitu_plot_event`, `sample`, `leaf_traits` |
| `spectra.csv` | `pixel`, `extracted_spectra` |

---

## File Specifications

### `campaign_metadata.csv`

One row per campaign + sensor combination. Campaign-level fields (`primary_funding_source`,
`data_repository`, `doi`, `taxa_system`) repeat across rows when a campaign has multiple sensors.

| Column | Table | Nullable | Enum |
|--------|-------|----------|------|
| `campaign_name` | `campaign` | No | |
| `primary_funding_source` | `campaign` | No | |
| `data_repository` | `campaign` | Yes | `Repository` |
| `doi` | `campaign` | Yes | |
| `taxa_system` | `campaign` | Yes | |
| `sensor_name` | `sensor_campaign` | No | `Sensor_name` |
| `elevation_source` | `sensor_campaign` | No | `ELEVATION_source` |

**Primary key:** `(campaign_name, sensor_name)`

---

### `wavelengths.csv`

One row per band per campaign + sensor. Bands must be in ascending order — the pipeline
assembles them positionally into `wavelength_center[]` and `fwhm[]` on `sensor_campaign`.

`(campaign_name, sensor_name)` must exist in `campaign_metadata.csv` in this bundle or in
`sensor_campaign` in the database.

| Column | Table | Nullable |
|--------|-------|----------|
| `campaign_name` | `sensor_campaign` | No |
| `sensor_name` | `sensor_campaign` | No |
| `band` | `sensor_campaign` | No |
| `wavelength` | `sensor_campaign.wavelength_center` | No |
| `fwhm` | `sensor_campaign.fwhm` | No |

`band` is a 0-based integer. All bands for a given `(campaign_name, sensor_name)` must be
contiguous (`0, 1, 2, ..., N`) with no gaps or duplicates.

**Primary key:** `(campaign_name, sensor_name, band)`

---

### `granule_metadata.csv`

One row per granule. `(campaign_name, sensor_name)` must exist in `sensor_campaign` (from
this bundle or the database).

| Column | Nullable | Enum |
|--------|----------|------|
| `granule_id` | No | |
| `campaign_name` | No | |
| `sensor_name` | No | `Sensor_name` |
| `acquisition_date` | No | |
| `acquisition_start_time` | No | |
| `cloudy_conditions` | No | `CLOUD_conditions` |
| `cloud_type` | No | `CLOUD_type` |
| `gsd` | No | |
| `raster_epsg` | No | |
| `flightline_id` | Yes | |
| `granule_rad_url` | Yes | |
| `granule_refl_url` | Yes | |

**Primary key:** `granule_id`

---

### `plots.geojson`

A GeoJSON FeatureCollection in EPSG:4326. Each feature represents one plot-granule
intersection. Accepted geometry types are **Point** and **Polygon**.

**Processing steps per feature:**
1. Geometry → `plot_shape`, returns `plot_shape_id`
2. `(plot_name, campaign_name, site_id, plot_method)` → `plot`, returns `plot_id`
3. `(plot_id, granule_id, plot_shape_id, intersection fields)` → `plot_raster_intersect`

**Required feature properties:**

| Property | Table | Nullable | Enum |
|----------|-------|----------|------|
| `plot_name` | `plot` | No | |
| `campaign_name` | `plot` | No | |
| `site_id` | `plot` | No | |
| `plot_method` | `plot` | Yes | `PLOT_method` |
| `granule_id` | `plot_raster_intersect` | No | |
| `extraction_method` | `plot_raster_intersect` | No | `EXTRACTION_method` |
| `delineation_method` | `plot_raster_intersect` | No | `DELINEATION_method` |
| `shape_aligned_to_granule` | `plot_raster_intersect` | No | |

`granule_id` must exist in `granule_metadata.csv` in this bundle or in `granule` in the database.

**Example feature:**
```json
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[-119.1, 37.5], [-119.1, 37.51], [-119.09, 37.51], [-119.09, 37.5], [-119.1, 37.5]]]
  },
  "properties": {
    "plot_name": "PLOT_001",
    "campaign_name": "SHIFT",
    "site_id": "ID",
    "plot_method": "Plot",
    "granule_id": "ang20230601t180000",
    "extraction_method": "Internal centroids",
    "delineation_method": "In Field",
    "shape_aligned_to_granule": true
  }
}
```

---

### `traits.csv`

One row per trait measurement. Plot event and sample fields repeat across rows for the same
sample. `(plot_name, campaign_name)` resolves `plot_id` — the plot must exist in
`plots.geojson` in this bundle or in `plot` in the database.

**Processing steps:**
1. Resolve `plot_id` from `(plot_name, campaign_name)`
2. `(plot_id, collection_date, plot event fields)` → `insitu_plot_event`
3. `(plot_id, collection_date, sample fields)` → `sample`
4. `(plot_id, collection_date, sample_name, trait fields)` → `leaf_traits`

| Column | Table | Nullable | Enum |
|--------|-------|----------|------|
| `plot_name` | *(resolve plot_id)* | No | |
| `campaign_name` | *(resolve plot_id)* | No | |
| `collection_date` | `insitu_plot_event`, `sample`, `leaf_traits` | No | |
| `plot_veg_type` | `insitu_plot_event` | No | `VEGETATION_type` |
| `subplot_cover_method` | `insitu_plot_event` | No | `SUBPLOT_cover_method` |
| `floristic_survey` | `insitu_plot_event` | No | |
| `sample_name` | `sample`, `leaf_traits` | No | |
| `taxa` | `sample` | No | `TAXA` |
| `veg_or_cover_type` | `sample` | No | `VEG_or_cover_type` |
| `phenophase` | `sample` | No | `PHENOPHASE` |
| `sample_fc_class` | `sample` | No | `FRACTIONAL_class` |
| `sample_fc_percent` | `sample` | No | |
| `plant_status` | `sample` | No | `PLANT_status` |
| `canopy_position` | `sample` | No | `CANOPY_position` |
| `trait` | `leaf_traits` | No | `Trait` |
| `value` | `leaf_traits` | No | |
| `method` | `leaf_traits` | No | `Trait_method` |
| `handling` | `leaf_traits` | No | `Sample_handling` |
| `units` | `leaf_traits` | No | `Trait_units` |
| `error` | `leaf_traits` | Yes | |
| `error_type` | `leaf_traits` | Yes | `Error_type` |

**Primary key:** `(plot_name, campaign_name, collection_date, sample_name, trait)`

---

### `spectra.csv`

One row per pixel. Band columns are positional integers using 0-based indexing (`0, 1, 2, ...`).
The number of band columns must match `wavelength_center` length in `sensor_campaign` for the
given `(campaign_name, sensor_name)`.

`(plot_name, campaign_name)` resolves `plot_id`. The `(plot_id, granule_id)` combination must
exist in `plot_raster_intersect` (from this bundle or the database).

**Processing steps:**
1. Resolve `plot_id` from `(plot_name, campaign_name)`
2. Verify `(plot_id, granule_id)` exists in `plot_raster_intersect`
3. Geometry and angle fields → `pixel`, returns `pixel_id`
4. Band columns assembled as `FLOAT4[]` → `extracted_spectra.radiance`

| Column | Table | Nullable |
|--------|-------|----------|
| `plot_name` | *(resolve plot_id)* | No |
| `campaign_name` | *(resolve plot_id)* | No |
| `sensor_name` | *(band count check)* | No |
| `granule_id` | `pixel` | No |
| `glt_row` | `pixel` | No |
| `glt_column` | `pixel` | No |
| `lon` | `pixel` | No |
| `lat` | `pixel` | No |
| `elevation` | `pixel` | No |
| `shade_mask` | `pixel` | No |
| `path_length` | `pixel` | No |
| `to_sensor_azimuth` | `pixel` | No |
| `to_sensor_zenith` | `pixel` | No |
| `to_sun_azimuth` | `pixel` | No |
| `to_sun_zenith` | `pixel` | No |
| `solar_phase` | `pixel` | No |
| `slope` | `pixel` | No |
| `aspect` | `pixel` | No |
| `utc_time` | `pixel` | No |
| `cosine_i` | `pixel` | No |
| `raw_cosine_i` | `pixel` | Yes |
| `0, 1, ... N` | `extracted_spectra.radiance` | No |

**Primary key:** `(campaign_name, plot_name, granule_id, glt_row, glt_column)`

---

## Processing Order

Files are validated and staged in strict dependency order. Steps marked with `*` capture
database-generated IDs and pass them to the next dependent step.

```
1. campaign_metadata.csv
       campaign
       sensor_campaign  (elevation_source only; wavelength_center/fwhm from step 2)

2. wavelengths.csv
       sensor_campaign  (populates wavelength_center[] and fwhm[])

3. granule_metadata.csv
       granule

4. plots.geojson  (one feature per plot-granule intersection)
       plot_shape *           → plot_shape_id per feature
       plot *                 → plot_id on first insert, reused for same plot
       plot_raster_intersect  ← plot_id + plot_shape_id

       plot_id_map: (campaign_name, plot_name) → plot_id
                    |                          |
                    v                          v
5. traits.csv                       6. spectra.csv
       insitu_plot_event                    pixel *  → pixel_id per row
       sample                               extracted_spectra  ← pixel_id
       leaf_traits
```

---

## QAQC Checks

All checks run for every file before any data is written. All errors are collected into a
single report — the pipeline does not stop at the first failing file.

### Universal checks (every CSV file)

| Check | Detail |
|-------|--------|
| Required columns present | All non-nullable columns must exist as headers. If any are missing, remaining checks for that file are skipped |
| No missing values | No blank or null cells in required columns |
| Values castable to correct type | float, int, bool, date (`YYYY-MM-DD`), time (`HH:MM:SS`) |
| Enum values valid | Values in enum columns must be in the set loaded from the database at runtime |
| No duplicate rows | Rows that would violate the file's primary key |
| No unexpected columns | Columns not declared in the file spec produce a warning and will not be ingested |

### `campaign_metadata.csv`

| Check | Detail |
|-------|--------|
| `campaign_name` not already in database | Must not already exist in production `campaign` table |
| `(campaign_name, sensor_name)` not already in database | Must not already exist in production `sensor_campaign` |

### `wavelengths.csv`

| Check | Detail |
|-------|--------|
| `(campaign_name, sensor_name)` resolves | Must exist in this bundle or in production `sensor_campaign` |
| `(campaign_name, sensor_name)` not already in database | Must not already exist in production `sensor_campaign` |
| Band indices 0-based contiguous | For each sensor group: sorted bands must equal `[0, 1, ..., N]` with no gaps |
| Wavelengths monotonically increasing | Wavelength values must be strictly ascending when sorted by band |
| Wavelength range | All wavelength values must be within 350–2600 nm. Values outside this range almost certainly indicate the wrong unit (µm instead of nm) or corrupted data |
| FWHM range | All fwhm values must be within 0.1–100 nm. Catches the µm/nm unit mistake (e.g. `0.01` when `10 nm` was intended). FWHM is not checked for monotonicity — it commonly varies non-monotonically across a sensor's spectral range |

### `granule_metadata.csv`

| Check | Detail |
|-------|--------|
| `(campaign_name, sensor_name)` resolves | Must exist in this bundle or in production `sensor_campaign` |
| `granule_id` not already in database | Must not already exist in production `granule` |

### `plots.geojson`

| Check | Detail |
|-------|--------|
| Valid FeatureCollection | Must be a GeoJSON FeatureCollection with at least one feature |
| All geometries are Points or Polygons | Other geometry types are rejected |
| Coordinates within WGS84 bounds | lon −180..180, lat −90..90 |
| Polygons topologically valid | Checked via Shapely. `make_valid` is attempted before failing |
| Polygon area > 0 | Degenerate zero-area polygons rejected |
| Required properties present | All required properties must be non-null |
| Enum property values valid | `extraction_method`, `delineation_method`, `plot_method` |
| `granule_id` resolves | Must exist in this bundle or in production `granule` |
| `(campaign_name, plot_name, granule_id)` unique | No duplicate plot-granule intersections within the file |
| `(campaign_name, plot_name, granule_id)` not in database | Would violate `plot_raster_intersect` primary key |
| `(campaign_name, plot_name)` already in database | Warning only — existing plots are reused via `ON CONFLICT DO NOTHING` |

### `traits.csv`

| Check | Detail |
|-------|--------|
| `(campaign_name, plot_name)` resolves | Must exist in this bundle or in production `plot` |
| `error_type` required when `error` is set | If `error` has a value, `error_type` must also be present |
| `(campaign_name, plot_name, collection_date)` not in database | Must not already exist in production `insitu_plot_event` |
| `(campaign_name, plot_name, collection_date, sample_name)` not in database | Must not already exist in production `sample` |
| `(campaign_name, plot_name, collection_date, sample_name, trait)` not in database | Must not already exist in production `leaf_traits` |

### `spectra.csv`

| Check | Detail |
|-------|--------|
| `(campaign_name, plot_name)` resolves | Must exist in this bundle or in production `plot` |
| `(campaign_name, plot_name, granule_id)` in `plot_raster_intersect` | The plot-granule intersection must exist in this bundle or in production |
| Band columns 0-based contiguous | Sorted integer headers must equal `[0, 1, ..., N]` |
| Band count matches wavelength count | Number of band columns must equal the band count for `(campaign_name, sensor_name)` |
| No duplicate pixels within file | `(campaign_name, plot_name, granule_id, glt_row, glt_column)` must be unique |
| No existing pixels in database | Same key must not already exist in production `pixel` |
| Pixel coordinates within WGS84 bounds | `lon`/`lat` must be within −180..180 and −90..90 |
| Pixel footprint intersects plot shape | A GSD × GSD square centred on the pixel centroid (`lon`/`lat`) must intersect the plot polygon. Matches rioxarray `all_touched=True` semantics — edge pixels whose footprint overlaps the boundary are accepted. Falls back to a centroid-only check if GSD is unknown. Pixels with no intersection are a blocking error |

---

## Adding a New Check

Each bundle file has its own check module in `qaqc/app/checks/`. A check module is a plain
Python file with one public function and any number of private helper functions below it.

**1. Add a helper to `universal.py` if the logic is reusable across files:**

```python
# universal.py
def check_my_new_rule(df: pd.DataFrame, file_name: str) -> list[dict]:
    """One sentence describing what this checks."""
    errors = []
    for idx, row in df.iterrows():
        if <condition>:
            errors.append({
                "file": file_name, "row": idx + 2,
                "column": "column_name", "message": "human-readable description",
            })
    return errors
```

**2. Add a private function to the relevant check module and call it from `check()`:**

```python
# traits.py
def check(context: CheckContext) -> CheckResult:
    df = context.data["traits"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    errors += _check_plot_fk(df, context)
    errors += _check_error_type_conditional(df)
    errors += _check_my_new_rule(df)           # ← add one line here
    return CheckResult("traits", len(df), errors, warnings)

def _check_my_new_rule(df: pd.DataFrame) -> list[dict]:
    """One sentence describing what this checks."""
    ...
```

**3. To add a check for an entirely new bundle file:**

1. Create `checks/config/<file_name>.json` declaring `required_cols`, `nullable_cols`,
   `enum_cols`, `type_cols`, `pk_cols`
2. Create `checks/<file_name>.py` with a `check(context) -> CheckResult` function
3. Add it to `CHECKS` in `checks/runner.py`

The docstring at the top of each check file lists every check that runs in plain English —
keep it up to date when adding checks.

---

## Enum Values

Enum types are defined in `schema/plants_v5_types.sql` and loaded from the database at
runtime by the QAQC Lambda (`db.py:load_enums`). The database is the single source of truth
for valid enum values — adding a new sensor name or taxa to the DB automatically makes it
valid in the next QAQC run.

Because enum types are defined at the database level they are shared between the
`vswir_plants` and `vswir_plants_staging` schemas. A single `ALTER TYPE` statement covers
both — there is no separate staging step for enums, and promotion does not touch enum types.

### Adding new enum values

Use `schema/add_enum_values.py`. The script takes a YAML file and a Secrets Manager ARN,
connects directly to the database, and runs `ALTER TYPE ... ADD VALUE IF NOT EXISTS` for
each declared value. It is idempotent — values that already exist are skipped.

```bash
# 1. Create a YAML file declaring the values to add
cat > new_values.yaml << 'EOF'
Sensor_name:
  - "AVIRIS-5"
TAXA:
  - "Quercus robur"
EOF

# 2. Dry run first to see what would be added
python schema/add_enum_values.py new_values.yaml \
  --secret-arn <secret-arn> \
  --dry-run

# 3. Apply
python schema/add_enum_values.py new_values.yaml \
  --secret-arn <secret-arn>
```

**Important notes:**
- PostgreSQL only supports adding enum values, not removing or renaming them. Renaming
  requires recreating the type — that is a manual migration.
- New values are appended to the end of the sort order.
- The QAQC Lambda caches enum values per warm container. After adding new values, a Lambda
  cold start (redeploy or function update) is needed to pick them up immediately.
- `viewConfig.js` in the frontend contains a hardcoded copy of enum values used for query
  filter dropdowns. Update it manually after adding new values.

---

## Pipeline Architecture

```
React Admin Page (superadmins Cognito group only)
  - Upload panel: file inputs for all 6 files, submit button
  - Batch list: status, QAQC report, approve/reject buttons
  - QAQC_FAIL batches: per-file replace panel + Recheck Bundle button
         |
         v
POST /ingest  (API Gateway → Ingest Trigger Lambda)
         |
         v
Ingest Trigger Lambda
  - Validates superadmins Cognito group
  - Assigns batch_id (UUID)
  - Reads file slot definitions from S3 (ingestion/bundle_config.json)
  - Generates presigned S3 PUT URLs — client uploads files directly to S3
  - Writes DynamoDB record: status=PENDING
  - Invokes QAQC Lambda asynchronously (fire and forget)
  - Returns { batch_id, uploaded_by, uploaded_at } immediately
         |
         v  (async Lambda invoke)
QAQC Lambda
  - Updates DynamoDB: status=QAQC_RUNNING, increments run_count, sets last_checked_at
  - Downloads all 6 files from S3
  - Loads enum values from production DB
  - Loads production reference sets (campaign_sensor_set, granule_ids, plot sets, etc.)
  - Runs all checks in dependency order, collecting ALL errors before failing
  - Writes full qaqc_report.json to S3
  - If errors: updates DynamoDB status=QAQC_FAIL with summary + S3 report key
  - If pass: loads into vswir_plants_staging (pandas/geopandas bulk inserts)
  - Updates DynamoDB: status=QAQC_PASS with row counts + S3 report key
         |
         v  (UI polls for status, admin reviews QAQC report)
         |
         +--[QAQC_FAIL]--> Admin reviews structured error list in UI
         |                   - Errors show file, row number, column, and message
         |                   - Fix files locally and re-upload per-slot
         |                   - Click "Recheck Bundle" → resets to PENDING → re-runs QAQC
         |
POST /ingest/{batch_id}/approve  or  POST /ingest/{batch_id}/reject
         |
         +--[approve]--> Promotion Lambda
         |                 - Copies staging → production in dependency order
         |                 - Refreshes materialized view (plot_pixels_mv)
         |                 - Deletes staging rows for this batch_id
         |                 - Updates DynamoDB: status=PROMOTED
         |
         +--[reject]---> Rejection Lambda
                           - Deletes staging rows for this batch_id
                           - Updates DynamoDB: status=REJECTED
```

---

## API Routes

| Method | Path | Lambda | Auth |
|--------|------|--------|------|
| `GET`  | `/ingest/config` | Ingest Trigger | superadmins |
| `POST` | `/ingest/upload-urls` | Ingest Trigger | superadmins |
| `GET`  | `/ingest` | Ingest Trigger | superadmins |
| `GET`  | `/ingest/{batch_id}` | Ingest Trigger | superadmins |
| `GET`  | `/ingest/{batch_id}/file/{slot}/upload-url` | Ingest Trigger | superadmins |
| `POST` | `/ingest` | Ingest Trigger | superadmins |
| `POST` | `/ingest/{batch_id}/recheck` | Ingest Trigger | superadmins |
| `POST` | `/ingest/{batch_id}/approve` | Promotion | superadmins |
| `POST` | `/ingest/{batch_id}/reject` | Rejection | superadmins |

---

## DynamoDB Record

Batches are stored in the `vswir-plants-export-jobs` table with `job_type = ingestion_batch`.

```json
{
  "job_id":              "uuid (batch_id)",
  "job_type":            "ingestion_batch",
  "status":              "PENDING | QAQC_RUNNING | QAQC_PASS | QAQC_FAIL | PROMOTED | REJECTED",
  "uploaded_by":         "cognito username",
  "uploaded_at":         "2026-04-03T00:00:00+00:00",
  "created_at":          "2026-04-03T00:00:00+00:00",
  "run_count":           2,
  "last_checked_at":     "2026-04-03T12:30:00+00:00",
  "files":               ["campaign_metadata", "wavelengths", "..."],
  "qaqc_report": {
    "campaign_metadata": { "passed": true,  "row_count": 4 },
    "spectra":           { "passed": false, "row_count": 15420 }
  },
  "qaqc_report_s3_key":  "ingestion/{batch_id}/qaqc_report.json",
  "promoted_at":         "2026-04-03T01:00:00+00:00"
}
```

`qaqc_report` in DynamoDB is a lightweight pass/fail + row count summary. The full structured
error and warning detail is stored in S3 at `qaqc_report_s3_key`. `GET /ingest/{batch_id}`
returns a presigned URL for the full report.

**Status lifecycle:**
```
PENDING → QAQC_RUNNING → QAQC_PASS → PROMOTED
                       ↘ QAQC_FAIL → (files replaced + recheck) → PENDING → ...

Any non-PROMOTED status → REJECTED
```

---

## Bundle Config

File slot definitions live in S3 so adding a new file to the bundle requires only an S3
update — no code deploy.

**S3 path:** `s3://vswir-plants-config/ingestion/bundle_config.json`
**Local copy (for reference):** `api/backend/ingestion/bundle_config.json`

```json
{
  "file_slots": {
    "campaign_metadata": ".csv",
    "wavelengths":        ".csv",
    "granule_metadata":   ".csv",
    "plots":              ".geojson",
    "traits":             ".csv",
    "spectra":            ".csv"
  }
}
```

Both the Ingest Trigger Lambda and the frontend read this config at runtime. The frontend
falls back to hardcoded defaults if the config endpoint fails.

---

## Code Structure

```
api/backend/ingestion/
  bundle_config.json             — file slot definitions (also in S3; local copy for reference)

  ingest_trigger/
    app/
      main.py                    — router: auth → route → handler
      auth.py                    — Cognito token validation
      multipart.py               — multipart/form-data body parsing
      store.py                   — S3 presigned URLs, DynamoDB reads/writes, Lambda invoke
    Dockerfile
    requirements.txt

  qaqc/
    app/
      main.py                    — handler + orchestration
      s3_files.py                — file download, parsing, report writing
      dynamo.py                  — DynamoDB status updates (run_count, last_checked_at)
      db.py                      — database connection + enum loader (cached per container)
      db_refs.py                 — production reference set loaders
      staging.py                 — bulk inserts into vswir_plants_staging
      checks/
        types.py                 — CheckContext, CheckResult dataclasses
        universal.py             — shared check functions + load_config + run_mechanical_checks
        runner.py                — ordered check execution; register new checks here
        campaign.py
        wavelengths.py
        granule.py
        plots.py
        traits.py
        spectra.py
        config/                  — per-file JSON schemas (required_cols, enums, pk_cols, ...)
          campaign_metadata.json
          wavelengths.json
          granule_metadata.json
          plots.json
          traits.json
          spectra.json
    Dockerfile
    requirements.txt

  promotion/
    app/
      main.py                    — handler: auth → validate → promote → mark done
      promote.py                 — staging → production transaction (pandas/geopandas)
    Dockerfile
    requirements.txt

  rejection/
    app/
      main.py                    — handler: auth → validate → delete staging → mark rejected
    requirements.txt

schema/
  plants_v5_types.sql            — PostgreSQL enum type definitions
  plants_v5_tables.sql           — production schema
  staging_tables.sql             — staging schema (mirrors production + batch_id column)
  staging_views.sql              — staging views used by promotion
  views.sql                      — production views and materialized views
  add_enum_values.py             — CLI tool for appending new enum values
```

