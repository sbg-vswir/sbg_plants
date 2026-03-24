# Data Ingestion Pipeline

## Overview

Data is submitted as a bundle of 6 files.

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

**Tables:** `campaign`, `sensor_campaign`

One row per campaign + sensor combination. Campaign-level fields repeat across rows when a campaign has multiple sensors.

| Column | Table | Nullable | Enum |
|--------|-------|----------|------|
| `campaign_name` | `campaign` | No | |
| `primary_funding_source` | `campaign` | No | |
| `data_repository` | `campaign` | Yes | Yes |
| `doi` | `campaign` | Yes | |
| `taxa_system` | `campaign` | Yes | |
| `sensor_name` | `sensor_campaign` | No | Yes |
| `elevation_source` | `sensor_campaign` | No | Yes |

---

### `wavelengths.csv`

**Tables:** `sensor_campaign` (`wavelength_center`, `fwhm`)

One row per band per campaign + sensor combination. Rows must be ordered by band index (ascending) — the ingestion pipeline assembles them positionally into the `wavelength_center[]` and `fwhm[]` arrays on the matching `sensor_campaign` row. The `(campaign_name, sensor_name)` pair must exist in `campaign_metadata.csv` in this bundle or in `sensor_campaign` in the database.

| Column | Table | Nullable |
|--------|-------|----------|
| `campaign_name` | `sensor_campaign` | No |
| `sensor_name` | `sensor_campaign` | No |
| `band` | *(ordering only)* | No |
| `wavelength` | `sensor_campaign.wavelength_center` | No |
| `fwhm` | `sensor_campaign.fwhm` | No |

`band` is a 0-based integer index. All bands for a given `(campaign_name, sensor_name)` must be present and contiguous with no gaps.

---

### `granule_metadata.csv`

**Tables:** `granule`

One row per granule. `campaign_name` + `sensor_name` must exist in `sensor_campaign` (from the current bundle or the database).

| Column | Nullable | Enum |
|--------|----------|------|
| `granule_id` | No | |
| `campaign_name` | No | |
| `sensor_name` | No | Yes |
| `acquisition_date` | No | |
| `acquisition_start_time` | No | |
| `cloudy_conditions` | No | Yes |
| `cloud_type` | No | Yes |
| `gsd` | No | |
| `raster_epsg` | No | |
| `flightline_id` | Yes | |
| `granule_rad_url` | Yes | |
| `granule_refl_url` | Yes | |

---

### `plots.geojson`

**Tables:** `plot_shape`, `plot`, `plot_raster_intersect`

A GeoJSON FeatureCollection of Polygons in EPSG:4326. Each feature represents one plot-granule intersection. The geometry is stored in `plot_shape`. Plot identity and raster intersection metadata are stored as feature properties.

**Processing steps per feature:**
1. Geometry → `plot_shape`, returns `plot_shape_id`
2. `plot_name` + `campaign_name` + `site_id` + `plot_method` → `plot`, returns `plot_id`
3. `plot_id` + `granule_id` + `plot_shape_id` + intersection fields → `plot_raster_intersect`

**Required feature properties:**

| Property | Table | Nullable | Enum |
|----------|-------|----------|------|
| `plot_name` | `plot` | No | |
| `campaign_name` | `plot` | No | |
| `site_id` | `plot` | No | |
| `plot_method` | `plot` | Yes | Yes |
| `granule_id` | `plot_raster_intersect` | No | |
| `extraction_method` | `plot_raster_intersect` | No | Yes |
| `delineation_method` | `plot_raster_intersect` | No | Yes |
| `shape_aligned_to_granule` | `plot_raster_intersect` | No | |

`granule_id` must exist in `granule` (from the current bundle or the database).

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

**Tables:** `insitu_plot_event`, `sample`, `leaf_traits`

One row per trait measurement. Plot event and sample fields repeat across rows for the same sample.

`plot_name` + `campaign_name` is used to resolve `plot_id`. The plot must exist in `plot` (from the current bundle or the database).

**Processing steps:**
1. Resolve `plot_id` from `plot_name` + `campaign_name`
2. `plot_id` + plot event fields → `insitu_plot_event` (insert if not already present for this `plot_id` + `collection_date`)
3. `plot_id` + `collection_date` + sample fields → `sample` (insert if not already present for this PK)
4. `plot_id` + `collection_date` + `sample_name` + trait fields → `leaf_traits`

| Column | Table | Nullable | Enum |
|--------|-------|----------|------|
| `plot_name` | *(resolve plot_id)* | No | |
| `campaign_name` | *(resolve plot_id)* | No | |
| `collection_date` | `insitu_plot_event`, `sample`, `leaf_traits` | No | |
| `plot_veg_type` | `insitu_plot_event` | No | Yes |
| `subplot_cover_method` | `insitu_plot_event` | No | Yes |
| `floristic_survey` | `insitu_plot_event` | No | |
| `sample_name` | `sample`, `leaf_traits` | No | |
| `taxa` | `sample` | No | Yes |
| `veg_or_cover_type` | `sample` | No | Yes |
| `phenophase` | `sample` | No | Yes |
| `sample_fc_class` | `sample` | No | Yes |
| `sample_fc_percent` | `sample` | No | |
| `plant_status` | `sample` | No | Yes |
| `trait` | `leaf_traits` | No | Yes |
| `value` | `leaf_traits` | No | |
| `method` | `leaf_traits` | No | Yes |
| `handling` | `leaf_traits` | No | Yes |
| `units` | `leaf_traits` | No | Yes |
| `error` | `leaf_traits` | Yes | |
| `error_type` | `leaf_traits` | Yes | Yes |

---

### `spectra.csv`

**Tables:** `pixel`, `extracted_spectra`

One row per pixel. Band columns are positional integers using 0-based indexing (`0, 1, 2, ...`). The number of band columns must match the length of `wavelength_center` in `sensor_campaign` for the given `campaign_name` + `sensor_name`.

`plot_name` + `campaign_name` is used to resolve `plot_id`. The `plot_id` + `granule_id` combination must exist in `plot_raster_intersect` (from the current bundle or the database).

**Processing steps:**
1. Resolve `plot_id` from `plot_name` + `campaign_name`
2. Verify `plot_id` + `granule_id` exists in `plot_raster_intersect`
3. All geometry and angle fields → `pixel`, returns `pixel_id`
4. Band columns (`0, 1, ... N`) assembled as `FLOAT4[]` → `extracted_spectra.radiance`

| Column | Table | Nullable | Enum |
|--------|-------|----------|------|
| `plot_name` | *(resolve plot_id)* | No | |
| `campaign_name` | *(resolve plot_id)* | No | |
| `sensor_name` | *(resolve sensor_campaign)* | No | Yes |
| `granule_id` | `pixel` | No | |
| `glt_row` | `pixel` | No | |
| `glt_column` | `pixel` | No | |
| `lon` | `pixel` | No | |
| `lat` | `pixel` | No | |
| `elevation` | `pixel` | No | |
| `shade_mask` | `pixel` | No | |
| `path_length` | `pixel` | No | |
| `to_sensor_azimuth` | `pixel` | No | |
| `to_sensor_zenith` | `pixel` | No | |
| `to_sun_azimuth` | `pixel` | No | |
| `to_sun_zenith` | `pixel` | No | |
| `solar_phase` | `pixel` | No | |
| `slope` | `pixel` | No | |
| `aspect` | `pixel` | No | |
| `utc_time` | `pixel` | No | |
| `cosine_i` | `pixel` | Yes | |
| `raw_cosine_i` | `pixel` | Yes | |
| `0, 1, ... N` | `extracted_spectra.radiance` | No |

---

## Processing Order

Files are processed in strict dependency order. Tables marked with `*` have database-generated IDs that are captured at insert time and passed to the next dependent step.

```
1. campaign_metadata.csv
       campaign
       sensor_campaign  (elevation_source only; wavelength_center/fwhm populated in step 2)

2. wavelengths.csv
       sensor_campaign  (populates wavelength_center[] and fwhm[] for each campaign+sensor)

3. granule_metadata.csv
       granule

4. plots.geojson  (one feature per plot-granule intersection)
       plot_shape *           -> plot_shape_id captured per feature
       plot *                 -> plot_id captured on first insert, reused for same plot
       plot_raster_intersect  <- plot_id + plot_shape_id

       plot_id_map built in memory: (campaign_name, plot_name) -> plot_id
                    |                          |
                    v                          v
5. traits.csv                       6. spectra.csv
       insitu_plot_event                    pixel *  -> pixel_id captured per batch
       sample                               extracted_spectra  <- pixel_id
       leaf_traits
```

## QAQC Checks

Checks are run for every file and all errors are collected into the `qaqc_report`. If a file cannot be parsed (invalid CSV, invalid GeoJSON) the remaining checks for that file are skipped.

### All Files

| Check | Detail |
|-------|--------|
| Required columns present | All non-nullable columns from the file spec must be present as headers |
| No missing values in required fields | Any blank cell in a non-nullable column is an error |
| Values castable to correct type | All values must be castable to the expected type for that column (e.g. float, integer, boolean, date) |
| Enum values valid | All enum columns must contain a value from the database enum. Valid values are loaded from the database at runtime |
| No duplicate rows | Rows that would violate a primary key or unique constraint in production are an error |

### `campaign_metadata.csv`

*(No file-specific checks beyond the universal checks.)*

---

### `wavelengths.csv`

| Check | Detail |
|-------|--------|
| `(campaign_name, sensor_name)` resolves | Must exist in `campaign_metadata.csv` in this bundle or in `sensor_campaign` in production |
| `band` values are contiguous from 0 | For each `(campaign_name, sensor_name)` group, band indices must be 0-based integers with no gaps or duplicates |
| `wavelength` and `fwhm` are numeric | Both columns must be castable to float for every row |

### `granule_metadata.csv`

| Check | Detail |
|-------|--------|
| `acquisition_date` parseable | Must be a valid date in `YYYY-MM-DD` format |
| `acquisition_start_time` parseable | Must be a valid time in `HH:MM:SS` format |
| `(campaign_name, sensor_name)` resolves | Must exist in `campaign_metadata.csv` in this bundle or in `sensor_campaign` in production |

### `plots.geojson`

| Check | Detail |
|-------|--------|
| Valid GeoJSON FeatureCollection | Must parse as a valid GeoJSON FeatureCollection |
| All geometries are Polygons | Non-polygon geometries are rejected |
| Coordinates within WGS84 bounds | All coordinate pairs must have lon between -180 and 180 and lat between -90 and 90, confirming the geometry is in EPSG:4326 |
| Polygons are topologically valid | Polygons must be non-self-intersecting and have a valid ring structure |
| `granule_id` resolves | Must exist in `granule_metadata.csv` in this bundle or in `granule` in production |
| No duplicate `(campaign_name, plot_name, granule_id)` features | `plot_raster_intersect` has a primary key of `(plot_id, granule_id)` so the same plot cannot be intersected with the same granule twice |

### `traits.csv`

| Check | Detail |
|-------|--------|
| `collection_date` parseable | Must be a valid date in `YYYY-MM-DD` format |
| `(plot_name, campaign_name)` resolves | Must exist in `plots.geojson` in this bundle or in `plot` in production |
| `error_type` present when `error` is set | If `error` has a value, `error_type` must also be set |

### `spectra.csv`

| Check | Detail |
|-------|--------|
| `(plot_name, campaign_name)` resolves | Must exist in `plots.geojson` in this bundle or in `plot` in production |
| `(plot_name, campaign_name, granule_id)` exists in `plot_raster_intersect` | The plot-granule intersection must have been established in `plots.geojson` or already exist in production |
| Band column count matches wavelength count | The number of band columns (0-based integers) must equal the number of rows for the corresponding `(campaign_name, sensor_name)` in `wavelengths.csv` (or the length of `wavelength_center` in `sensor_campaign` if resolving from the database) |
| Band values are numeric | All band cells must be castable to float |
| Pixel coordinates within plot shape | Each pixel's `lon`/`lat` must fall within the polygon of the `plot_shape` linked via `(plot_name, campaign_name, granule_id)` in `plot_raster_intersect` |

---

## Pipeline Architecture

Ingestion is managed through a dedicated admin page in the React frontend, restricted to users in the admins Cognito group. Files are uploaded via the UI, validated asynchronously, and promoted to production only after admin review and approval.

```
React Admin Page (admins Cognito group only)
  - upload view: file inputs for all 6 files, submit button
  - batch list view: shows all jobs with status, QAQC report, approve/reject buttons
         |
         v
POST /ingest  (API Gateway)
         |
         v
Ingest Trigger Lambda
  - validates Cognito token, confirms admins group membership
  - assigns batch_id (UUID)
  - writes all 6 files to S3: ingestion/{batch_id}/raw/
  - creates DynamoDB record: status=PENDING
  - returns batch_id to UI immediately (QAQC runs asynchronously)
         |
         v  (S3 event trigger)
QAQC Lambda
  - reads raw files from S3, validates in memory (see QAQC Checks)
  - checks referential integrity against both the batch and production DB
  - if checks pass: loads into vswir_plants_staging within a single transaction
  - if checks fail: no data is written to the database
  - updates DynamoDB: status=QAQC_PASS or QAQC_FAIL with per-file report
         |
         v  (UI polls for status, admin reviews QAQC report)
POST /ingest/{batch_id}/approve  or  /ingest/{batch_id}/reject
         |
         +--[approve]-->  Promotion Lambda
         |                  - copies staging to production in a single transaction
         |                  - re-runs insert-and-capture for serial IDs against production sequences
         |                  - refreshes materialized view (plot_pixels_mv)
         |                  - removes staging rows for this batch_id
         |                  - updates DynamoDB: status=PROMOTED
         |
         +--[reject]-->  Rejection Lambda
                           - removes staging rows for this batch_id
                           - updates DynamoDB: status=REJECTED
```

### DynamoDB `ingestion-jobs` Table

| Attribute | Type | Notes |
|-----------|------|-------|
| `batch_id` | String (PK) | UUID |
| `status` | String | `PENDING`, `QAQC_RUNNING`, `QAQC_PASS`, `QAQC_FAIL`, `PROMOTED`, `REJECTED` |
| `uploaded_by` | String | Cognito username |
| `uploaded_at` | String | ISO timestamp |
| `files` | List | Filenames present in the batch |
| `qaqc_report` | Map | Errors, warnings, row counts per file |
| `promoted_at` | String | ISO timestamp, set on promotion |
