# Database Views — `views_v2.sql`

All views live in the `vswir_plants` schema. Grants are managed separately in `grant.sql`.

---

## 1. `trait_view`

**Purpose:** Exposes trait measurements alongside their associated sample, plot event,
and plot identity. All samples are included regardless of whether they have trait
measurements. Assumes all plot events will have a sample, if not that would not be displayed.

**Anchor table:** `sample`

**Join chain:**
```
sample
  JOIN insitu_plot_event ON (plot_id, collection_date)
  JOIN plot ON plot_id
  LEFT JOIN leaf_traits ON (plot_id, collection_date, sample_name)
```

**Row count:** One row per `(sample, trait)`. Samples without trait measurements appear
once with NULL trait columns. Row count is between `sample` count (1,262) and
`sample + leaf_traits` count depending on how many traits per sample exist.

**Columns:**

| Column | Source | Notes |
|---|---|---|
| `plot_id` | `plot` | |
| `plot_name` | `plot` | |
| `campaign_name` | `plot` | |
| `site_id` | `plot` | |
| `plot_method` | `plot` | |
| `collection_date` | `insitu_plot_event` | |
| `plot_veg_type` | `insitu_plot_event` | |
| `subplot_cover_method` | `insitu_plot_event` | |
| `floristic_survey` | `insitu_plot_event` | |
| `sample_name` | `sample` | |
| `taxa` | `sample` | |
| `veg_or_cover_type` | `sample` | |
| `phenophase` | `sample` | |
| `sample_fc_class` | `sample` | |
| `sample_fc_percent` | `sample` | |
| `canopy_position` | `sample` | |
| `plant_status` | `sample` | |
| `trait` | `leaf_traits` | NULL if no trait measurement |
| `value` | `leaf_traits` | NULL if no trait measurement |
| `units` | `leaf_traits` | NULL if no trait measurement |
| `method` | `leaf_traits` | NULL if no trait measurement |
| `handling` | `leaf_traits` | NULL if no trait measurement |
| `error` | `leaf_traits` | NULL if no trait measurement |
| `error_type` | `leaf_traits` | NULL if no trait measurement |

---

## 2. `plot_shape_view`

**Purpose:** Exposes plot identity and geometry. `DISTINCT` collapses
the fan-out from `plot_raster_intersect` back to one row per `(plot, shape)`.

**Anchor table:** `plot`

**Join chain:**
```
plot
  JOIN plot_raster_intersect ON plot_id
  JOIN plot_shape ON plot_shape_id
DISTINCT ON (plot_id, plot_shape_id)
```

**Row count:** One row per `(plot, shape)` — length of `plot_shape` table.

**Columns:**

| Column | Source | Notes |
|---|---|---|
| `plot_id` | `plot` | |
| `plot_name` | `plot` | |
| `campaign_name` | `plot` | |
| `site_id` | `plot` | |
| `plot_method` | `plot` | |
| `plot_shape_id` | `plot_shape` | |
| `geom` | `plot_shape` | Geometry (polygon or point) |

**Note on performance:** At current scale (~100 granules, ~2,074 `plot_raster_intersect`
rows) this view is fast as a regular view. If `plot_raster_intersect` grows significantly
an index on `plot_raster_intersect(plot_id)` should be considered.

---

## 3. `granule_view`

**Purpose:** Exposes granule metadata. One row per granule, no pixel aggregation.
Pixel IDs are aggregated at query time in `POST /query` after spatial and attribute
filtering has been applied — not pre-aggregated here.

Campaign/sensor metadata (`wavelength_center`, `fwhm`) is available separately via
`extracted_metadata_view` and joined when needed.

**Anchor table:** `granule`

**Row count:** One row per granule — length of `granule` table (~100 rows currently).

**Columns:**

| Column | Source | Notes |
|---|---|---|
| `granule_id` | `granule` | |
| `campaign_name` | `granule` | |
| `sensor_name` | `granule` | |
| `acquisition_date` | `granule` | |
| `acquisition_start_time` | `granule` | |
| `cloudy_conditions` | `granule` | |
| `cloud_type` | `granule` | |
| `gsd` | `granule` | Ground sample distance |
| `flightline_id` | `granule` | |
| `granule_rad_url` | `granule` |  |
| `granule_refl_url` | `granule` |  |
| `raster_epsg` | `granule` | Coordinate reference system |

---

## 4. `extracted_spectra_view`

**Purpose:** Exposes per-pixel radiance spectra alongside pixel metadata. Used by
`POST /query/spectra` — an async route that dispatches to SQS, runs the query in a
worker Lambda, and uploads results as a CSV to S3.

**Row count:** One row per pixel (can be very large — millions of rows).

**Columns:**

| Column | Source |
|---|---|
| `pixel_id` | `extracted_spectra` |
| `campaign_name` | `granule` |
| `sensor_name` | `granule` |
| `granule_id` | `pixel` |
| `acquisition_date` | `granule` |
| `acquisition_start_time` | `granule` |
| `plot_id` | `pixel` |
| `plot_name` | `plot` |
| `lon` | `pixel` |
| `lat` | `pixel` |
| `elevation` | `pixel` |
| `path_length` | `pixel` |
| `to_sensor_azimuth` | `pixel` |
| `to_sensor_zenith` | `pixel` |
| `to_sun_azimuth` | `pixel` |
| `to_sun_zenith` | `pixel` |
| `solar_phase` | `pixel` |
| `slope` | `pixel` |
| `aspect` | `pixel` |
| `cosine_i` | `pixel` |
| `utc_time` | `pixel` |
| `shade_mask` | `pixel` |
| `radiance` | `extracted_spectra` | `FLOAT4[]` — one value per band |

---

## 5. `extracted_metadata_view`

**Purpose:** Exposes sensor wavelength centers and FWHM values used by the frontend to
build spectra CSV column headers. Used by `GET /query/metadata`.

**Row count:** One row per `(campaign, sensor)`.

**Columns:**

| Column | Source |
|---|---|
| `campaign_name` | `sensor_campaign` |
| `sensor_name` | `sensor_campaign` |
| `elevation_source` | `sensor_campaign` |
| `wavelength_center` | `sensor_campaign` | `FLOAT4[]` — one value per band |
| `fwhm` | `sensor_campaign` | `FLOAT4[]` — one value per band |

---

## 6. `reflectance_view`

**Purpose:** Exposes per-pixel reflectance spectra alongside pixel metadata. Used by
`POST /query/reflectance` — same async pattern as `extracted_spectra_view`.

**Row count:** One row per pixel with reflectance output (subset of all pixels).

**Columns:**

| Column | Source |
|---|---|
| `pixel_id` | `output_pixel_rfl` |
| `campaign_name` | `granule` |
| `sensor_name` | `granule` |
| `granule_id` | `pixel` |
| `acquisition_date` | `granule` |
| `acquisition_start_time` | `granule` |
| `plot_id` | `pixel` |
| `plot_name` | `plot` |
| `lon` | `pixel` |
| `lat` | `pixel` |
| `elevation` | `pixel` |
| `cloudy_conditions` | `granule` |
| `cloud_type` | `granule` |
| `reflectance` | `output_pixel_rfl` | `FLOAT4[]` — one value per band |
