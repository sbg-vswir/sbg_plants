# VSWIR Plants — Query System Brief

A complete reference for a fresh agent. Covers the backend query API, frontend query UI,
and outstanding work. Read this alongside the ingestion brief at
`api/backend/ingestion/INGESTION_V2.md` for the full picture.

---

## Architecture Overview

```
Browser (React + MUI + Leaflet)
  │
  │  Cognito JWT (Bearer token)
  ▼
API Gateway
  ├── POST /query                → database_api Lambda  (linked query)
  ├── POST /query/{view}         → database_api Lambda  (single-view query or async SQS dispatch)
  ├── GET  /query/metadata       → database_api Lambda  (wavelength metadata)
  ├── GET  /job_status/{jobId}   → worker Lambda        (poll spectra/download job)
  ├── POST /run_isofit           → isofit Lambda
  └── GET  /isofit_jobs          → isofit Lambda

database_api Lambda  ──► PostgreSQL (vswir_plants schema)
                     ──► SQS (async spectra/reflectance jobs)

worker Lambda  ◄─── SQS trigger
               ──► S3 (presigned download URLs)
               ──► DynamoDB (job status)
```

AWS:
- Profile: `smce-airborne`, region: `us-west-2`
- Lambda: `vswir-plants-database-api`
- ECR: `445567107118.dkr.ecr.us-west-2.amazonaws.com/vswir-plants-api:latest`

---

## Database Schema (vswir_plants)

Key tables and views used by the query system:

| Object | Type | Description |
|--------|------|-------------|
| `plot` | table | One row per plot (plot_id, campaign_name, plot_name, site_id) |
| `plot_shape` | table | Plot geometry (Polygon or Point, EPSG:4326) |
| `plot_raster_intersect` | table | Plot ↔ granule intersection metadata |
| `granule` | table | One row per flight granule (granule_id, campaign, sensor, date) |
| `pixel` | table | One row per pixel (granule_id, plot_id, glt_row, glt_column, lon, lat, ...) |
| `leaf_traits` | table | Trait measurements (sample_name, plot_id, trait, value, units, ...) |
| `sample` | table | Sample metadata |
| `insitu_plot_event` | table | Plot visit events |
| `extracted_spectra` | table | Per-pixel radiance arrays (FLOAT4[]) |
| `plot_shape_view` | view | Plots + geometry — used for spatial filter |
| `trait_view` | view | Joined traits/sample/plot_event — all trait columns |
| `granule_view` | view | Granule metadata |
| `extracted_spectra_view` | view | Per-pixel radiance + positional metadata (async only) |
| `reflectance_view` | view | Per-pixel reflectance (async only) |
| `extracted_metadata_view` | view | Wavelength / FWHM metadata |

Known data issue: 41 of 102 granules in `East River 2018 / NEON AIS 1` have
`acquisition_date = 1970-01-01` (epoch zero from bad ingest). These granules have no rows
in `pixel` and will not appear in query results. Will be corrected in a future data fix.

---

## Backend — `api/backend/database_api/`

```
app/
  main.py          — Lambda handler + route dispatch
  orchestration.py — 4-stage linked query engine
  filter.py        — build_where_clause dispatcher
  filter_utils.py  — low-level SQL clause builders
  view_config.py   — VIEW_CONFIG: column types, date columns, async flags
  query.py         — build_query + execute_query
  db.py            — psycopg2 connection via Secrets Manager
  sqs.py           — send_sqs for async spectra/reflectance jobs
```

### Route Dispatch (`main.py`)

| Method | Path | Handler |
|--------|------|---------|
| `POST` | `/query` | `handle_linked_query` → `orchestration.run_linked_query` |
| `POST` | `/query/spectra` | `handle_view_query("extracted_spectra_view")` → SQS async |
| `POST` | `/query/reflectance` | `handle_view_query("reflectance_view")` → SQS async |
| `GET`  | `/query/metadata` | `handle_view_query("extracted_metadata_view")` → sync |
| `POST/GET` | `/query/{view}` | `handle_view_query(view)` → sync or async per view config |

### Linked Query (`orchestration.py`)

The main query engine. `run_linked_query(body)` runs 4 stages:

```
Stage 1  — spatial filter on plot_shape_view → all matching plot_ids
Stage 1b — if trait_filters: narrow to plots with matching traits (parallel if both)
           if granule_filters: narrow to plots with matching granules
Stage 2  — parallel COUNT queries → total_traits, total_granules
Stage 3  — paginate plot_ids[offset:offset+limit]
Stage 4  — parallel: fetch plots (geojson/json) + traits + granules for page only
```

Granule queries use a CTE to filter `granule_view` before joining `pixel`:

```sql
WITH filtered_granules AS (
    SELECT granule_id, campaign_name, sensor_name, acquisition_date,
           acquisition_start_time, cloudy_conditions, cloud_type
    FROM vswir_plants.granule_view
    WHERE <granule_filters>
)
SELECT fg.*, array_agg(DISTINCT px.plot_id) AS plot_ids,
             array_agg(px.pixel_id ORDER BY px.pixel_id) AS pixel_ids
FROM filtered_granules fg
JOIN vswir_plants.pixel px ON px.granule_id = fg.granule_id
WHERE px.plot_id = ANY(%s)
GROUP BY fg.granule_id, ...
```

**Important:** granules returned are scoped to the current page's plot_ids. The full
`fetchLinkedQueryAll` (no limit/offset) is used for pixel count, CSV row count, and
Extract Spectra — it hits all plots at once.

### Filter System

`build_where_clause(view_name, filters)` in `filter.py` validates filters against
`VIEW_CONFIG` and dispatches to clause builders in `filter_utils.py`:

| Field type | Clause |
|------------|--------|
| `string` | `= %s` or `IN (%s, ...)` |
| `array` | `= ANY(%s)` |
| `numeric` | `=`, `IN`, `BETWEEN`, or range dict `{min, max}` |
| `boolean` | `= %s` |
| `date` | `= %s` or `IN` |
| `start_date` / `end_date` | `>= %s` / `<= %s` |
| `geom` | bounding box + `ST_Intersects` (uses GiST index) |

### Request / Response

**Linked query request body:**
```json
{
  "campaign_name": "East River 2018",
  "geojson": { "type": "Polygon", "coordinates": [[...]] },
  "trait_filters": {
    "trait": ["LMA"],
    "taxa": ["Salix"],
    "collection_date_start": "2018-06-01",
    "collection_date_end": "2018-08-31"
  },
  "granule_filters": {
    "sensor_name": ["NEON AIS 1"],
    "cloudy_conditions": ["Clear"],
    "acquisition_date_start": "2018-06-01"
  },
  "format": "geojson",
  "limit": 100,
  "offset": 0
}
```

**Response:**
```json
{
  "total_plots": 477,
  "total_traits": 2001,
  "total_granules": 61,
  "truncated": true,
  "plots_geojson": { "type": "FeatureCollection", "features": [...] },
  "traits": [{ "plot_id": 1, "trait": "LMA", "value": 0.012, ... }],
  "granules": [{ "granule_id": "...", "plot_ids": [1,2,3], "pixel_ids": [101,102,...] }]
}
```

---

## Frontend — `api/frontend/react-app/src/`

```
pages/
  LinkedQueryPage.jsx   — THE query page (route: /)
  IsoFitPage.jsx        — IsoFit page (route: /isofit), same layout as LinkedQueryPage
  QueryPage.jsx         — Legacy single-view page (route commented out, DO NOT DELETE)
  AdminPage.jsx         — User management (Cognito)
  IngestPage.jsx        — Data ingestion pipeline UI

hooks/
  useLinkedQuery.js     — All state for LinkedQueryPage + IsoFitPage
  useSpectraExtraction.js
  useIsoFitJob.js
  useJobPolling.js
  useIsoFitPolling.js
  useIngestionPolling.js
  useIsAdmin.js

components/
  Navbar.jsx            — Tabs: Query (/), IsoFit (/isofit), Ingest (/ingest), Admin (/admin)
  LinkedFilterPanel.jsx — Collapsible trait + granule filters, spatial upload/draw
  LinkedDataTable.jsx   — Collapsible two-tab table (Traits / Granules)
  MapView.jsx           — Leaflet map, draw toolbar, zoom-scaled markers, polygon at zoom≥13
  PlotSidePanel.jsx     — Sticky side panel on plot click
  JobStatus.jsx         — Spectra extraction job cards
  IsoFitStatus.jsx      — IsoFit job monitoring panel
  IsoFitHistory.jsx     — Recent IsoFit jobs list

utils/
  api.js                — All API calls
  auth.js               — Cognito OAuth
  client.js             — Axios instance with auto token refresh
  helpers.js            — toRanges, parseFilters, convertToCSV, summarizeValue
  parquetUtils.js       — hyparquet decoder (read-only — cannot write parquet)
```

### Page Layout (LinkedQueryPage + IsoFitPage)

```
┌─ Navbar ─────────────────────────────────────────────────────┐
├─ Left (380px fixed) ──┬─ Right (flex) ────────────────────────┤
│ LinkedFilterPanel     │ [IsoFitStatus + IsoFitHistory]        │
│  - Campaign name      │  (IsoFitPage only, above map)         │
│  - Spatial filter     │                                       │
│  - Trait filters ▼    │ MapView                               │
│  - Granule filters ▼  │                                       │
│                       │ Action bar:                           │
│ [Apply]               │  Prev | N-M of Total | Next           │
│ [Reset]               │  pixel count | toggle | button        │
│                       │                                       │
│ N plots matched       │ JobStatus (spectra jobs)              │
│                       │                                       │
│                       │ LinkedDataTable (collapsible)         │
│                       ├─ PlotSidePanel (sticky, if selected) ─┤
└───────────────────────┴───────────────────────────────────────┘
```

Action bar buttons:
- **LinkedQueryPage**: Extract Spectra (`color="secondary"`) + Download CSV (`color="primary"`, shows row count)
- **IsoFitPage**: Run ISOFIT (`color="error"`, requires confirmation) — no Download CSV

### `useLinkedQuery.js` — Key State and Methods

```js
const q = useLinkedQuery();

// Filter state
q.campaignName, q.setCampaignName
q.traitFilters, q.setTraitFilters      // 14 fields
q.granuleFilters, q.setGranuleFilters  // 5 fields
q.geojsonContent                       // active spatial filter (drawn or uploaded)
q.setDrawnGeojson(geom)                // sets geojsonIsDrawn = true
q.setUploadedGeojson(geom)             // sets geojsonIsDrawn = false

// Pagination
q.offset, q.limit (100), q.displayedOffset
q.handleApply(), q.handleNext(), q.handlePrev(), q.handleReset()

// Response
q.plots, q.traits, q.granules
q.totalPlots, q.totalTraits, q.totalGranules
q.loading, q.error, q.setError, q.hasQueried

// Selected plot
q.selectedPlotId, q.setSelectedPlotId
q.selectedTraits, q.selectedGranules

// Map
q.mapData          // GeoJSON FeatureCollection for current page plots
q.filterMapData    // GeoJSON for uploaded (not drawn) spatial filter

// Pixel counts (populated by background fetch after Apply)
q.pagePixelCount       // sync sum from current page granules
q.totalPixelCount      // null until background fetch completes
q.pixelCountLoading    // true while background fetch in flight

// CSV row count (populated by same background fetch)
q.totalCsvRows         // null until background fetch completes

// Async methods
await q.getPixelRanges()          // → { "campaign|sensor": [[start,end],...] }
await q.getMergedDownloadData()   // → all rows, all pages, traits × granules merged
```

**Background fetch:** fires immediately after `handleApply`. Calls `fetchLinkedQueryAll`
(no limit/offset) once, caches result in `allGranulesCache` + `allTraitsCache` refs.
Subsequent calls to `getPixelRanges` and `getMergedDownloadData` use the cache — no second
API call. Both caches cleared on `handleReset`.

### `utils/api.js` — Key Functions

```js
// Linked query — paginated
fetchLinkedQuery(payload)       // POST /query with limit/offset
fetchLinkedQueryAll(payload)    // POST /query with limit:100000, offset:0

// Spectra extraction (async — returns job_id per sensor)
extractSpectra(pixelRangesBySensor, spectraType)

// Job polling
pollJobStatus(jobId, mode)      // GET /job_status/{jobId}?mode=...

// IsoFit
submitIsofitRun({ pixel_ranges })
listIsofitJobs(limit)
```

### Known Bugs / Quirks

- **`leaflet-draw` ES module bug**: `readableArea` references bare `type` global.
  Fixed with `window.type = ''` patch in `MapView.jsx`.
- **Rectangle drawing conflicts with map drag**: Fixed with `map.dragging.disable()` on
  `DRAWSTART` / `enable()` on `DRAWSTOP`.
- **Drawn shape duplicate polygon**: drawn layer lives in Leaflet `drawnItems` FeatureGroup
  AND was being rendered as a `filterData` GeoJSON layer. Fixed by `geojsonIsDrawn` flag —
  `filterData` only renders for uploaded shapes.

---

## viewConfig.js (Frontend) ↔ view_config.py (Backend)

Both files must be kept in sync. The frontend `viewConfig.js` has a hardcoded copy of
all enum values used for filter dropdowns. When new enum values are added to the database
via `schema/add_enum_values.py`, `viewConfig.js` must be updated manually.

The backend `view_config.py` is the authoritative source for column types, filterable
fields, and async flags. The frontend `viewConfig.js` mirrors this for the legacy
`QueryPage` only — `LinkedQueryPage` uses a hardcoded filter list in `LinkedFilterPanel`.

---

## Posssible issues 

### 1. Async download pipeline

**Problem:** `getMergedDownloadData` calls `fetchLinkedQueryAll` which is a synchronous
`POST /query` with `limit: 100000`. For large datasets this risks hitting the 29s API
Gateway timeout and the 10MB response limit. The current CSV download also runs the
full trait × granule cross-join in the browser.

**Proposed fix:** Move all downloads to an async worker pattern, same as spectra extraction.

Backend changes:
- `app/sqs.py` — add `send_linked_download_sqs(body, format)` with `job_type: linked_download`
- `app/main.py` — add `POST /query/download` route returning `{ job_id }`
- `worker_lambda/app/linked_download.py` — NEW — runs 4-stage orchestration, cross-joins
  traits × granules, streams result to S3 via multipart upload, writes presigned URL to DynamoDB

Frontend changes:
- `utils/api.js` — add `startLinkedDownload(payload, format)`
- `hooks/useLinkedQuery.js` — replace `getMergedDownloadData` with async job + polling
- `pages/LinkedQueryPage.jsx` — Download button shows progress, polls until done,
  triggers browser download from presigned URL

### 2. GeoJSON / GeoParquet download formats

**Problem:** Currently Download CSV is the only format. Users may want GeoJSON (plots +
traits geometry) or GeoParquet (for use in Python/R workflows). The frontend uses
`hyparquet` which is read-only — it cannot write parquet in the browser.

**Proposed fix:** Once item 1 (async worker) is done, the worker can write any format
to S3. The download request body should include a `format` field:
- `csv` — flat CSV, one row per trait × granule (current behaviour)
- `geojson` — FeatureCollection, one feature per plot, traits + granules as properties
- `geoparquet` — GeoDataFrame written by geopandas + pyarrow, best for Python/R

The browser just fetches the presigned S3 URL directly — no client-side encoding needed.
The format toggle lives in the action bar next to the Download button.