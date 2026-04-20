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
`/views/{view_name}`. One view, one query, existing filter logic unchanged. Any view
defined in `VIEW_CONFIG` can be queried this way.

---

## Route Map

| Route | Method | Description |
|---|---|---|
| `/query` | `POST` | 3-stage linked plot/trait/granule query |
| `/query/{view_name}` | `POST` | Single-view query (replaces `/views/{view_name}`) |
| `/query/spectra` | `POST` | Async radiance spectra extraction |
| `/query/reflectance` | `POST` | Async reflectance extraction |
| `/query/metadata` | `GET` | Sensor wavelength/fwhm metadata |

Route precedence: `/query/spectra`, `/query/reflectance`, and `/query/metadata` are
matched before the `{view_name}` wildcard. `/query` (exact) is matched before all
`/query/...` sub-paths.

---

## Views Used

See `schema/VIEWS.md` for full column definitions.

| View | Used by | Description |
|---|---|---|
| `plot_shape_view` | `POST /query` Stage 1, `POST /query/plot_shape_view` | Plot identity + geometry, one row per (plot, shape) |
| `trait_view` | `POST /query` Stage 2a, `POST /query/trait_view` | Traits + samples + plot events |
| `granule_view` | `POST /query` Stage 2b, `POST /query/granule_view` | Granule metadata, no pixel aggregation |
| `extracted_spectra_view` | `POST /query/spectra` | Per-pixel radiance (async) |
| `extracted_metadata_view` | `GET /query/metadata`, `POST /query/extracted_metadata_view` | Sensor wavelength/fwhm |
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
- **Pixel IDs aggregated at query time** — granule pixel IDs are computed at Stage 2b
  by joining `granule_view` to the `pixel` table filtered to matched `plot_id`s.
  This ensures `pixel_ids` per granule only contains pixels from the matched plots.
- **All existing filterable columns supported** — existing filter machinery unchanged.
  Trait columns passed under `trait_filters`, granule columns under `granule_filters`.
  `campaign_name` is the exception — passed at the top level, applied to all stages.
- **Two independent date filters** — `collection_date_start/end` (sample collection)
  and `acquisition_date_start/end` (granule flight date) filtered separately.
- **`format` controls `plots` encoding only** — in the linked query response, `plots`
  is encoded as GeoParquet bytes or a GeoJSON FeatureCollection depending on `format`.
  `traits` and `granules` are always plain JSON arrays regardless of `format`.
- **Total counts always returned** — `COUNT(*)` run before `limit`/`offset` so the
  frontend can display "showing plots 1–100 of 1,247".
- **100 plot limit by default** — keeps responses synchronous and fast. Configurable
  via `limit`. Use `offset` to page through results.
- **`offset` supported** — applies to Stage 1 (the plot query). Traits and granules
  are always returned in full for the offset-paginated plot set.
- **Error responses** — always `{"error": "...message..."}`. Client errors (bad input,
  invalid filter columns, invalid GeoJSON) return `400`. Server errors return `500`.

---

## `POST /query` — 3-Stage Linked Query

### The 3 Stages

**Stage 1 — Spatial filter**
Query `plot_shape_view` with optional GeoJSON geometry and optional `campaign_name`.
Returns all `plot_id`s whose shapes intersect the spatial filter. All matched plots
proceed to Stage 2 regardless of whether they have traits or granules.

**Stage 2 — Parallel trait + granule queries**
Two queries run against the `plot_id`s from Stage 1:
- Trait query — filters `trait_view` by `plot_id = ANY(stage1_ids)` + any
  `trait_filters` provided.
- Granule query — joins `granule_view` to the `pixel` table, filtered by
  `pixel.plot_id = ANY(stage1_ids)` + any `granule_filters` provided. Pixel IDs
  are aggregated per granule via `array_agg`.

If no `trait_filters` provided → all traits for stage1 plots returned.
If no `granule_filters` provided → all granules for stage1 plots returned.

**Stage 3 — Response assembly**
Total counts captured from Stage 2 results before `limit`/`offset` are applied.
`limit`/`offset` applied to the Stage 1 plot list. Traits and granules filtered to
match the final paginated plot set. All arrays assembled into the response.

### Request

```json
{
  "campaign_name": "East River 2018",
  "geojson": {
    "type": "Polygon",
    "coordinates": [[[...]]]
  },
  "trait_filters": {
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
    "sensor_name":            ["NEON AIS 1"],
    "cloudy_conditions":      ["Not recorded"],
    "cloud_type":             ["Not Collected"],
    "acquisition_date_start": "2018-06-01",
    "acquisition_date_end":   "2018-08-31"
  },
  "limit":  100,
  "offset": 0,
  "format": "geojson"
}
```

### Fields

| Field | Required | Description |
|---|---|---|
| `campaign_name` | No | Applied to all three stages — plots, traits, and granules |
| `geojson` | No | GeoJSON geometry (Polygon or MultiPolygon). Omit for no spatial filter. |
| `trait_filters` | No | Filters applied to `trait_view`. All sub-fields optional. |
| `granule_filters` | No | Filters applied to granule/pixel query. All sub-fields optional. |
| `limit` | No | Max number of plots per page. Default 100. |
| `offset` | No | Plot offset for pagination. Default 0. |
| `format` | No | `"geojson"` (default) or `"geoparquet"`. Controls encoding of `plots` only. |

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
      "plot_name": "020-ER18",
      "sample_name": "020-ER18_Piceaengelmannii",
      "collection_date": "2018-06-27",
      "trait": "LMA",
      "value": 412.9,
      "units": "g/m2",
      "method": "Weight based",
      "handling": "Oven dried",
      "error": null,
      "error_type": null,
      "taxa": "Picea engelmannii",
      "veg_or_cover_type": "PV",
      "phenophase": "Leaves fully expanded",
      "sample_fc_class": "pv",
      "sample_fc_percent": 95.0,
      "canopy_position": "Not recorded",
      "plant_status": "Not recorded",
      "plot_veg_type": "Tree",
      "subplot_cover_method": "Not recorded",
      "floristic_survey": false
    }
  ],
  "granules": [
    {
      "granule_id": "NIS01_20180621_172130",
      "campaign_name": "East River 2018",
      "sensor_name": "NEON AIS 1",
      "acquisition_date": "2018-06-21",
      "cloudy_conditions": "Green",
      "cloud_type": "Not Collected",
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

### Response (`format: "geoparquet"`)

`plots` is replaced by a base64-encoded GeoParquet byte string. `traits` and `granules`
remain plain JSON arrays.

```json
{
  "plots_geoparquet":    "<base64-encoded geoparquet bytes>",
  "traits": [...],
  "granules": [...],
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

Drop-in replacement for `POST /views/{view_name}`. Accepts `filters`, `select`,
`limit`, `offset`, `format` in the request body. All existing filterable columns
for each view are supported. Any view defined in `VIEW_CONFIG` is a valid `view_name`.

Available views: `plot_shape_view`, `trait_view`, `granule_view`,
`extracted_metadata_view`, `extracted_spectra_view`, `reflectance_view`

Supported `format` values per view:

| View | `geojson` | `geoparquet` | `json` | `parquet` |
|---|---|---|---|---|
| `plot_shape_view` | yes | yes | — | — |
| `trait_view` | — | — | yes | yes |
| `granule_view` | — | — | yes | yes |
| `extracted_metadata_view` | — | — | yes | yes |
| `extracted_spectra_view` | — | — | async | async |
| `reflectance_view` | — | — | async | async |

Geo/non-geo format selection is automatic — if the view has a `geom` column and
`format` is `geojson` or `geoparquet`, the geometry is included. Otherwise plain
JSON/Parquet is returned.

---

## `POST /query/spectra` — Async Radiance Extraction

Async route. Dispatches to SQS → worker Lambda runs the query against
`extracted_spectra_view` → results uploaded as CSV to S3 → presigned URL returned
via `GET /job_status/{job_id}`.

Request body: same as `POST /query/{view_name}` with `view_name = extracted_spectra_view`.
`metadata` field (sensor wavelength/fwhm JSON) must be included — fetch it first via
`GET /query/metadata` and pass it along.

---

## `POST /query/reflectance` — Async Reflectance Extraction

Same async pattern as `/query/spectra` but queries `reflectance_view`.

---

## `GET /query/metadata` — Sensor Metadata

Synchronous. Returns wavelength centers and FWHM for a given campaign/sensor combination.
Used by the frontend to build spectra CSV column headers before dispatching an async
spectra or reflectance extraction job.

Query parameters: `campaign_name`, `sensor_name`

Response: JSON array of `{ campaign_name, sensor_name, elevation_source, wavelength_center, fwhm }`.
