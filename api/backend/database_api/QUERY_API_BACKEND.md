# `/query` API — Backend Implementation Plan

## Overview

All changes are in the existing `database_api` Lambda. No new infrastructure or
deployment units. The existing `POST /views/{view_name}` route is replaced by
`POST /query/{view_name}`. A new `POST /query` route handles the 3-stage linked query.

---

## Files Changing

| File | Change |
|---|---|
| `app/main.py` | Route dispatch — detect `/query` vs `/query/{view_name}` vs `/query/spectra` etc. |
| `app/orchestration.py` | **New** — 3-stage linked query logic |
| `app/filter_utils.py` | Add `_build_array_in_clause` for `plot_id = ANY(%s)` |
| `app/filter.py` | Handle `collection_date_start/end`, `acquisition_date_start/end`, `array` type |
| `app/view_config.py` | Add `trait_view`, `plot_shape_view`, `granule_view`. Add `plot_id` array type to relevant views |
| `schema/views_v2.sql` | New views — see `schema/VIEWS.md` |
| `schema/grant.sql` | Grants for new views to `postgrest_user` |
| `terraform_deployment/modules/api/main.tf` | Update API Gateway routes from `/views/...` to `/query/...` |

---

## `app/main.py`

Route dispatch logic replaces the existing single `POST /views/{view_name}` handler:

```python
path = event.get("path", "")

if path == "/query":
    return handle_linked_query(event)
elif path == "/query/spectra":
    return handle_view_query(event, view_name="extracted_spectra_view")
elif path == "/query/reflectance":
    return handle_view_query(event, view_name="reflectance_view")
elif path == "/query/metadata":
    return handle_view_query(event, view_name="extracted_metadata_view")
elif path.startswith("/query/"):
    view_name = path.split("/query/")[1]
    return handle_view_query(event, view_name=view_name)
```

`handle_view_query` is the existing single-query logic, unchanged except for receiving
`view_name` as a parameter rather than reading it from `pathParameters`.

`handle_linked_query` parses `geojson`, `trait_filters`, `granule_filters`, `limit`,
`format` from the request body and calls `run_linked_query()` from `orchestration.py`.

---

## `app/orchestration.py` (new)

```python
def run_linked_query(geojson, trait_filters, granule_filters, limit=100, debug=False):

    # Stage 1 — spatial filter → plot_ids
    stage1_filters = {}
    if geojson:
        stage1_filters["geom"] = geojson
    if trait_filters.get("campaign_name"):
        stage1_filters["campaign_name"] = trait_filters["campaign_name"]
    plots_df = _execute("plot_shape_view", stage1_filters)
    stage1_plot_ids = plots_df["plot_id"].tolist()

    if not stage1_plot_ids:
        return empty_response()

    # Stage 2a — trait query
    tf = {**trait_filters, "plot_id": stage1_plot_ids}
    # map collection_date_start/end → start_date/end_date for filter.py
    traits_df = _execute("trait_view", _remap_dates(tf, "collection_date"))

    # Stage 2b — granule query (joins granule_view to plot_raster_intersect)
    gf = {**granule_filters, "plot_id": stage1_plot_ids}
    granules_df = _execute_granule_query(_remap_dates(gf, "acquisition_date"))

    # Count queries (before limit)
    total_plot_count    = len(stage1_plot_ids)
    total_trait_count   = len(traits_df)
    total_granule_count = len(granules_df)

    # Apply limit
    final_plot_ids = stage1_plot_ids[:limit]
    truncated = len(stage1_plot_ids) > limit

    # Final assembly — filter to final_plot_ids
    final_plots    = plots_df[plots_df["plot_id"].isin(final_plot_ids)]
    final_traits   = traits_df[traits_df["plot_id"].isin(final_plot_ids)]
    final_granules = _aggregate_pixels(granules_df, final_plot_ids)

    return {
        "plots":               final_plots,
        "traits":              final_traits,
        "granules":            final_granules,
        "plot_count":          len(final_plot_ids),
        "trait_count":         len(final_traits),
        "granule_count":       len(final_granules),
        "total_plot_count":    total_plot_count,
        "total_trait_count":   total_trait_count,
        "total_granule_count": total_granule_count,
        "truncated":           truncated,
    }
```

`_aggregate_pixels(granules_df, plot_ids)` — runs a direct SQL query:
```sql
SELECT
    p.granule_id,
    g.campaign_name,
    g.sensor_name,
    g.acquisition_date,
    g.cloudy_conditions,
    g.cloud_type,
    array_agg(DISTINCT pri.plot_id) AS plot_ids,
    jsonb_agg(px.pixel_id ORDER BY px.pixel_id) AS pixel_ids
FROM vswir_plants.plot_raster_intersect pri
JOIN vswir_plants.granule g ON g.granule_id = pri.granule_id
JOIN vswir_plants.pixel px
    ON px.granule_id = pri.granule_id
    AND px.plot_id = pri.plot_id
WHERE pri.plot_id = ANY(%s)
-- optional granule filters applied here
GROUP BY p.granule_id, g.campaign_name, g.sensor_name,
         g.acquisition_date, g.cloudy_conditions, g.cloud_type
```

This ensures `pixel_ids` only contains pixels from the matched plots, not all plots
for that granule.

---

## `app/filter_utils.py`

Add `_build_array_in_clause`:

```python
def _build_array_in_clause(col, ids, clauses, params):
    """
    Generates: "col" = ANY(%s)
    Uses a single Postgres array param instead of N individual %s placeholders.
    Used to pass plot_id lists between stages efficiently.
    """
    clauses.append(f'"{col}" = ANY(%s)')
    params.append(ids)
```

---

## `app/filter.py`

**Date alias handling** — `collection_date_start/end` and `acquisition_date_start/end`
are convenience aliases that map to `start_date`/`end_date` for the existing
`_build_date_range_clauses` logic:

```python
# Before the main filter loop, remap date aliases
if "collection_date_start" in filters:
    filters["start_date"] = filters.pop("collection_date_start")
if "collection_date_end" in filters:
    filters["end_date"] = filters.pop("collection_date_end")
# same for acquisition_date_start/end
```

**Array type dispatch** — add `"array"` to the type dispatch in the main filter loop:

```python
elif field_type == "array":
    _build_array_in_clause(col, val, clauses, params)
```

---

## `app/view_config.py`

Add three new views:

```python
"trait_view": {
    "has_geo":     False,
    "is_async":    False,
    "date_column": "collection_date",
    "columns": {
        "plot_id":              {"type": "array",   "filterable": True,  "selectable": True},
        "plot_name":            {"type": "string",  "filterable": True,  "selectable": True},
        "campaign_name":        {"type": "string",  "filterable": True,  "selectable": True},
        "site_id":              {"type": "string",  "filterable": True,  "selectable": True},
        "plot_method":          {"type": "string",  "filterable": True,  "selectable": True},
        "collection_date":      {"type": "date",    "filterable": True,  "selectable": True},
        "plot_veg_type":        {"type": "string",  "filterable": True,  "selectable": True},
        "subplot_cover_method": {"type": "string",  "filterable": True,  "selectable": True},
        "floristic_survey":     {"type": "boolean", "filterable": True,  "selectable": True},
        "sample_name":          {"type": "string",  "filterable": True,  "selectable": True},
        "taxa":                 {"type": "string",  "filterable": True,  "selectable": True},
        "veg_or_cover_type":    {"type": "string",  "filterable": True,  "selectable": True},
        "phenophase":           {"type": "string",  "filterable": True,  "selectable": True},
        "sample_fc_class":      {"type": "string",  "filterable": True,  "selectable": True},
        "sample_fc_percent":    {"type": "numeric", "filterable": True,  "selectable": True},
        "canopy_position":      {"type": "string",  "filterable": True,  "selectable": True},
        "plant_status":         {"type": "string",  "filterable": True,  "selectable": True},
        "trait":                {"type": "string",  "filterable": True,  "selectable": True},
        "value":                {"type": "numeric", "filterable": True,  "selectable": True},
        "units":                {"type": "string",  "filterable": True,  "selectable": True},
        "method":               {"type": "string",  "filterable": True,  "selectable": True},
        "handling":             {"type": "string",  "filterable": True,  "selectable": True},
        "error":                {"type": "numeric", "filterable": False, "selectable": True},
        "error_type":           {"type": "string",  "filterable": True,  "selectable": True},
    },
},

"plot_shape_view": {
    "has_geo":     True,
    "is_async":    False,
    "columns": {
        "plot_id":       {"type": "array",  "filterable": True,  "selectable": True},
        "plot_name":     {"type": "string", "filterable": True,  "selectable": True},
        "campaign_name": {"type": "string", "filterable": True,  "selectable": True},
        "site_id":       {"type": "string", "filterable": True,  "selectable": True},
        "plot_method":   {"type": "string", "filterable": True,  "selectable": True},
        "plot_shape_id": {"type": "numeric","filterable": False, "selectable": True},
        "geom":          {"type": "geom",   "filterable": True,  "selectable": True},
    },
},

"granule_view": {
    "has_geo":     False,
    "is_async":    False,
    "date_column": "acquisition_date",
    "columns": {
        "granule_id":            {"type": "string",  "filterable": True,  "selectable": True},
        "campaign_name":         {"type": "string",  "filterable": True,  "selectable": True},
        "sensor_name":           {"type": "string",  "filterable": True,  "selectable": True},
        "acquisition_date":      {"type": "date",    "filterable": True,  "selectable": True},
        "acquisition_start_time":{"type": "string",  "filterable": False, "selectable": True},
        "cloudy_conditions":     {"type": "string",  "filterable": True,  "selectable": True},
        "cloud_type":            {"type": "string",  "filterable": True,  "selectable": True},
        "gsd":                   {"type": "numeric", "filterable": True,  "selectable": True},
        "flightline_id":         {"type": "string",  "filterable": True,  "selectable": True},
        "granule_rad_url":       {"type": "string",  "filterable": False, "selectable": True},
        "granule_refl_url":      {"type": "string",  "filterable": False, "selectable": True},
        "raster_epsg":           {"type": "numeric", "filterable": False, "selectable": True},
    },
},
```

---

## `schema/grant.sql`

Add grants for new views:

```sql
GRANT SELECT ON vswir_plants.trait_view       TO postgrest_user;
GRANT SELECT ON vswir_plants.plot_shape_view  TO postgrest_user;
GRANT SELECT ON vswir_plants.granule_view     TO postgrest_user;
```

---

## `terraform_deployment/modules/api/main.tf`

Update API Gateway routes:
- Remove `POST /views/{view_name}`
- Add `POST /query`
- Add `POST /query/{view_name}`
- Add `POST /query/spectra`
- Add `POST /query/reflectance`
- Add `GET /query/metadata`
