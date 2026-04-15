# `/query` API — Overview and Route Reference

## Overview

All API routes live under a unified `/query` namespace in the existing `database_api`
Lambda. The previous `/views/{view_name}` routes are replaced.

There are two categories of routes:

**`POST /query`** — 3-stage linked query. Returns plots, traits, and granules together.
The spatial filter (GeoJSON) is the primary constraint. Trait and granule filters are
optional — omitting them does not exclude that dimension, it just returns everything for
that dimension. All plots within the spatial area are returned. If a plot has no matching
traits its `traits` array is empty. If it has no matching granules its `granules` array
is empty.

**`POST /query/{view_name}`** — single-stage query. Same behavior as the old
`/views/{view_name}`. One view, one query, existing filter logic unchanged.

---

## Route Map

| Route | Method | Description |
|---|---|---|
| `/query` | `POST` | 3-stage linked plot/trait/granule query |
| `/query/{view_name}` | `POST` | Single-view query (replaces `/views/{view_name}`) |
| `/query/spectra` | `POST` | Async radiance spectra extraction |
| `/query/reflectance` | `POST` | Async reflectance extraction |
| `/query/metadata` | `GET` | Sensor wavelength/fwhm metadata |

---

## Views Used

See `schema/VIEWS.md` for full column definitions.

| View | Used by | Description |
|---|---|---|
| `trait_view` | `POST /query` Stage 2 | Traits + samples + plot events |
| `plot_shape_view` | `POST /query` Stage 1 | Plot shapes + granule aggregations |
| `granule_view` | `POST /query` Stage 2 | Granule metadata, no pixel aggregation |
| `extracted_spectra_view` | `POST /query/spectra` | Per-pixel radiance (async) |
| `extracted_metadata_view` | `GET /query/metadata` | Sensor wavelength/fwhm |
| `reflectance_view` | `POST /query/reflectance` | Per-pixel reflectance (async) |

---

## Key Design Decisions

- **Unified `/query` namespace** — all routes under `/query`. Same Lambda, no new
  infrastructure, no new deployment unit.
- **Regular JWT auth** — same JWT authorizer as all existing routes. No superadmin
  requirement.
- **Spatial filter is the primary constraint** — all plots within the spatial area are
  returned. Trait and granule filters narrow the `traits` and `granules` arrays but do
  not exclude plots. No strict intersection.
- **No pre-aggregated granules or pixel IDs** — granules and pixel IDs are aggregated at query time after
  filtering, so they always reflect only the matched plots.
- **All existing filterable columns supported** — existing filter machinery unchanged.
  Trait columns passed under `trait_filters`, granule columns under `granule_filters`.
- **Two independent date filters** — `collection_date` (sample collection) and
  `acquisition_date` (granule flight date) filtered separately.
- **Multiple response formats** — `geoparquet`, `parquet`, `geojson`, `json`.
- **Total counts always returned** — `COUNT(*)` queries before `limit` is applied so
  the frontend can display "showing 100 of 1,247 plots".
- **100 plot limit by default** — keeps responses synchronous and fast. Configurable
  via `limit`.

---

## `POST /query` — 3-Stage Linked Query

### The 3 Stages

**Stage 1 — Spatial filter**
Query `plot_shape_view` with optional GeoJSON geometry and optional `campaign_name`.
Returns all `plot_id`s whose shapes intersect the spatial filter. All matched plots
proceed to Stage 2 regardless of whether they have traits or granules.

**Stage 2 — Parallel trait + granule queries**
Two queries run against the `plot_id`s from Stage 1:
- Trait query — filters `trait_view` by trait/taxa/sample filters +
  `plot_id = ANY(stage1_ids)`
- Granule query — filters `granule_view` joined to `plot_raster_intersect` by
  sensor/date/cloud filters + `plot_id = ANY(stage1_ids)`

If no `trait_filters` provided → all traits for stage1 plots returned.
If no `granule_filters` provided → all granules for stage1 plots returned.

**Stage 3 — Response assembly**
No intersection — all stage1 plots are returned. Traits and granules assembled per plot.
Pixel IDs aggregated from `pixel` table filtered to `final_plot_ids` and grouped by
granule. Count queries run before limit is applied to get total counts.

### Request

```json
{
  "geojson": {
    "type": "Polygon",
    "coordinates": [[[...]]]
  },
  "trait_filters": {
    "campaign_name":         "East River 2018",
    "trait":                 ["LMA", "Chl"],
    "taxa":                  ["Picea engelmannii"],
    "veg_or_cover_type":     ["PV"],
    "phenophase":            ["Leaves fully expanded"],
    "plant_status":          ["Not recorded"],
    "canopy_position":       ["Not recorded"],
    "sample_fc_class":       ["pv"],
    "handling":              ["Oven dried"],
    "method":                ["Weight based"],
    "collection_date_start": "2018-06-01",
    "collection_date_end":   "2018-08-31"
  },
  "granule_filters": {
    "campaign_name":          "East River 2018",
    "sensor_name":            ["NEON AIS 1"],
    "cloudy_conditions":      ["Not recorded"],
    "cloud_type":             ["Not Collected"],
    "acquisition_date_start": "2018-06-01",
    "acquisition_date_end":   "2018-08-31"
  },
  "limit":  100,
  "format": "geoparquet"
}
```

### Response (`format: "geoparquet"`)

Three base64-encoded files returned directly in the HTTP response body:

```json
{
  "plots_parquet":       "<base64-encoded geoparquet bytes>",
  "traits_parquet":      "<base64-encoded parquet bytes>",
  "granules_parquet":    "<base64-encoded parquet bytes>",
  "plot_count":           100,
  "trait_count":          412,
  "granule_count":         18,
  "total_plot_count":    1247,
  "total_trait_count":   4832,
  "total_granule_count":   87,
  "truncated":            true
}
```

### Response (`format: "geojson"`)

```json
{
  "plots": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": { "type": "Polygon", "coordinates": [...] },
        "properties": {
          "plot_id": 21,
          "plot_name": "020-ER18",
          "campaign_name": "East River 2018",
          "site_id": "CRBU",
          "plot_method": "Individual"
        }
      }
    ]
  },
  "traits": [
    {
      "plot_id": 21,
      "sample_name": "020-ER18_Piceaengelmannii",
      "collection_date": "2018-06-27",
      "trait": "LMA",
      "value": 412.9,
      "units": "grams dry mass per g m2",
      "taxa": "Picea engelmannii"
    }
  ],
  "granules": [
    {
      "granule_id": "NIS01_20180621_172130",
      "campaign_name": "East River 2018",
      "sensor_name": "NEON AIS 1",
      "acquisition_date": "2018-06-21",
      "plot_ids": [21, 22],
      "pixel_ids": [3817, 3818, 3819, 3820]
    }
  ],
  "plot_count":           100,
  "trait_count":          412,
  "granule_count":         18,
  "total_plot_count":    1247,
  "total_trait_count":   4832,
  "total_granule_count":   87,
  "truncated":            true
}
```

### `plots` columns
`plot_id`, `plot_name`, `campaign_name`, `site_id`, `plot_method`, `geom`

### `traits` columns
`plot_id`, `plot_name`, `sample_name`, `collection_date`, `trait`, `value`, `units`,
`method`, `handling`, `error`, `error_type`, `taxa`, `veg_or_cover_type`, `phenophase`,
`sample_fc_class`, `sample_fc_percent`, `canopy_position`, `plant_status`,
`plot_veg_type`, `subplot_cover_method`, `floristic_survey`

### `granules` columns
`granule_id`, `campaign_name`, `sensor_name`, `acquisition_date`, `cloudy_conditions`,
`cloud_type`, `plot_ids` (integer array), `pixel_ids` (integer array)

---

## `POST /query/{view_name}` — Single-View Query

Same behavior as the old `POST /views/{view_name}`. Accepts `filters`, `select`,
`limit`, `offset`, `format` in the request body. All existing filterable columns
for each view are supported.

Available views: `trait_view`, `plot_shape_view`, `granule_view`,
`extracted_metadata_view`

---

## `POST /query/spectra` — Async Radiance Extraction

Async route. Dispatches to SQS → worker Lambda runs the query against
`extracted_spectra_view` → results uploaded as CSV to S3 → presigned URL returned
via `GET /job_status/{job_id}`.

Request body: same as `POST /query/{view_name}` with `view_name = extracted_spectra_view`.

---

## `POST /query/reflectance` — Async Reflectance Extraction

Same async pattern as `/query/spectra` but queries `reflectance_view`.

---

## `GET /query/metadata` — Sensor Metadata

Synchronous. Returns wavelength centers and FWHM for a given campaign/sensor.
Used by the frontend to build spectra CSV column headers.

Query parameters: `campaign_name`, `sensor_name`

---