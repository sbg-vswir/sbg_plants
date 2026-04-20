# `/query` API — Backend Implementation Plan

## Overview

All changes are in the existing `database_api` Lambda. No new infrastructure or
deployment units. The existing `POST /views/{view_name}` route is replaced by
`POST /query/{view_name}`. A new `POST /query` route handles the 3-stage linked query.

`plot_pixels_mv` (the old materialized view) is removed entirely. All routes now use
the views defined in `schema/views_v2.sql`.

---

## Files Changing

| File | Change |
|---|---|
| `app/main.py` | Route dispatch — detect `/query` vs `/query/{view_name}` vs `/query/spectra` etc. Catch `ValueError` from filter building as `400` not `500`. |
| `app/orchestration.py` | **New** — 3-stage linked query logic |
| `app/filter_utils.py` | Add `_build_array_in_clause` for `plot_id = ANY(%s)` |
| `app/filter.py` | Handle `collection_date_start/end`, `acquisition_date_start/end` date aliases. Add `array` type dispatch. |
| `app/view_config.py` | Replace `plot_pixels_mv` and `leaf_traits_view` with `plot_shape_view`, `trait_view`, `granule_view`. Update `extracted_spectra_view` and `reflectance_view` columns to match `views_v2.sql`. |
| `schema/grant.sql` | Add `SELECT` grants on new views and `pixel` table to `postgrest_user` |
| `terraform_deployment/modules/api/main.tf` | Update API Gateway routes from `/views/...` to `/query/...` |

---

## `app/main.py`

Route dispatch logic replaces the existing single `POST /views/{view_name}` handler.
Special paths take precedence over the `{view_name}` wildcard:

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

`handle_linked_query` parses `campaign_name`, `geojson`, `trait_filters`,
`granule_filters`, `limit`, `offset`, `format` from the request body and calls
`run_linked_query()` from `orchestration.py`.

### Error handling improvement

`ValueError` raised by `filter.py` (e.g. invalid filter column name) must be caught
separately and returned as `400 Bad Request` rather than the existing broad `500`:

```python
try:
    sql, params = build_query(...)
except ValueError as e:
    return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
except Exception as e:
    logger.exception("Database error")
    return {"statusCode": 500, "body": json.dumps({"error": f"Database error: {str(e)}"})}
```

The same pattern applies inside `handle_linked_query` — validation errors (invalid
GeoJSON, unrecognised filter keys) should return `400`, not `500`.

---

## `app/orchestration.py` (new)

Owns the 3-stage linked query. Called by `handle_linked_query` in `main.py`.

```python
def run_linked_query(campaign_name, geojson, trait_filters, granule_filters,
                     limit=100, offset=0, debug=False):

    # ── Stage 1 — Spatial filter → plot_ids ──────────────────────────────────
    stage1_filters = {}
    if geojson:
        stage1_filters["geom"] = geojson
    if campaign_name:
        stage1_filters["campaign_name"] = campaign_name

    plots_df = _execute("plot_shape_view", stage1_filters, debug=debug)
    all_plot_ids = plots_df["plot_id"].tolist()

    if not all_plot_ids:
        return _empty_response()

    total_plot_count = len(all_plot_ids)

    # ── Stage 2a — Trait query ────────────────────────────────────────────────
    # plot_id passed as array type → "plot_id" = ANY(%s)
    tf = {**(trait_filters or {}), "plot_id": all_plot_ids}
    tf = _remap_date_aliases(tf, "collection_date")
    traits_df = _execute("trait_view", tf, debug=debug)

    total_trait_count = len(traits_df)

    # ── Stage 2b — Granule + pixel aggregation ────────────────────────────────
    # Joins granule_view → pixel table, filtered to matched plot_ids.
    # Aggregates pixel_ids and plot_ids per granule so that pixel_ids only
    # contains pixels from the matched plots, not all plots for that granule.
    gf = granule_filters or {}
    gf = _remap_date_aliases(gf, "acquisition_date")
    granules_df = _execute_granule_query(all_plot_ids, gf, debug=debug)

    total_granule_count = len(granules_df)

    # ── Stage 3 — Paginate and assemble ──────────────────────────────────────
    paginated_plot_ids = all_plot_ids[offset : offset + limit]
    truncated = (offset + limit) < total_plot_count

    final_plots    = plots_df[plots_df["plot_id"].isin(paginated_plot_ids)]
    final_traits   = traits_df[traits_df["plot_id"].isin(paginated_plot_ids)]
    final_granules = granules_df[
        granules_df["plot_ids"].apply(
            lambda ids: bool(set(ids) & set(paginated_plot_ids))
        )
    ]

    return {
        "plots":               final_plots,
        "traits":              final_traits,
        "granules":            final_granules,
        "plot_count":          len(paginated_plot_ids),
        "trait_count":         len(final_traits),
        "granule_count":       len(final_granules),
        "total_plot_count":    total_plot_count,
        "total_trait_count":   total_trait_count,
        "total_granule_count": total_granule_count,
        "truncated":           truncated,
    }
```

### `_execute_granule_query(plot_ids, granule_filters, debug)`

Runs a direct SQL query — cannot use the generic `build_query` path because it needs
a cross-table aggregation that is not expressible as a single-view SELECT:

```sql
SELECT
    g.granule_id,
    g.campaign_name,
    g.sensor_name,
    g.acquisition_date,
    g.cloudy_conditions,
    g.cloud_type,
    array_agg(DISTINCT px.plot_id)          AS plot_ids,
    array_agg(px.pixel_id ORDER BY px.pixel_id) AS pixel_ids
FROM vswir_plants.granule_view g
JOIN vswir_plants.pixel px ON px.granule_id = g.granule_id
WHERE px.plot_id = ANY(%s)
-- optional granule_filters appended here (sensor_name, cloudy_conditions,
-- cloud_type, acquisition_date_start/end) via _build_granule_filter_clauses()
GROUP BY g.granule_id, g.campaign_name, g.sensor_name,
         g.acquisition_date, g.cloudy_conditions, g.cloud_type
```

`pixel` table must be accessible to `postgrest_user` (see grant changes below).

### `_remap_date_aliases(filters, date_prefix)`

Maps the convenience aliases to the `start_date`/`end_date` keys that
`_build_date_range_clauses` expects:

```python
def _remap_date_aliases(filters, prefix):
    """
    Maps e.g. "collection_date_start" → "start_date" for filter.py compatibility.
    prefix is "collection_date" or "acquisition_date".
    """
    f = dict(filters)
    if f"{prefix}_start" in f:
        f["start_date"] = f.pop(f"{prefix}_start")
    if f"{prefix}_end" in f:
        f["end_date"] = f.pop(f"{prefix}_end")
    return f
```

---

## `app/filter_utils.py`

Add `_build_array_in_clause`:

```python
def _build_array_in_clause(col, ids, clauses, params):
    """
    Generates: "col" = ANY(%s)
    Uses a single Postgres array param instead of N individual %s placeholders.
    Used to pass plot_id lists between query stages efficiently.
    psycopg2 automatically converts a Python list to a Postgres array.
    """
    clauses.append(f'"{col}" = ANY(%s)')
    params.append(ids)
```

---

## `app/filter.py`

**Array type dispatch** — add `"array"` to the type dispatch in the main filter loop
so `plot_id` lists from Stage 1 are handled correctly:

```python
elif field_type == "array":
    _build_array_in_clause(col, val, clauses, params)
```

**Date alias handling** — `collection_date_start/end` and `acquisition_date_start/end`
are remapped to `start_date`/`end_date` by `_remap_date_aliases` in `orchestration.py`
before reaching `filter.py`. No changes to `filter.py` itself are needed for the linked
query path. For the single-view `/query/{view_name}` path, clients should continue to
use `start_date`/`end_date` in their `filters` object as before.

---

## `app/view_config.py`

Replace `plot_pixels_mv` and `leaf_traits_view` with the three new v2 views.
Update `extracted_spectra_view` and `reflectance_view` to match `views_v2.sql` columns.

### Remove

- `plot_pixels_mv`
- `leaf_traits_view`

### Add `plot_shape_view`

```python
"plot_shape_view": {
    "has_geo":     True,
    "is_async":    False,
    "columns": {
        "plot_id":       {"type": "numeric", "filterable": False, "selectable": True},
        "plot_name":     {"type": "string",  "filterable": True,  "selectable": True},
        "campaign_name": {"type": "string",  "filterable": True,  "selectable": True},
        "site_id":       {"type": "string",  "filterable": True,  "selectable": True},
        "plot_method":   {"type": "string",  "filterable": True,  "selectable": True},
        "plot_shape_id": {"type": "numeric", "filterable": False, "selectable": True},
        "geom":          {"type": "geom",    "filterable": True,  "selectable": True},
    },
},
```

Note: `plot_id` is `"array"` type only when passed between orchestration stages
internally. For the single-view `/query/plot_shape_view` route it is `"numeric"` and
not directly filterable by external clients (to avoid confusion with the array type).

### Add `trait_view`

```python
"trait_view": {
    "has_geo":     False,
    "is_async":    False,
    "date_column": "collection_date",
    "columns": {
        "plot_id":              {"type": "numeric", "filterable": False, "selectable": True},
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
```

### Add `granule_view`

```python
"granule_view": {
    "has_geo":     False,
    "is_async":    False,
    "date_column": "acquisition_date",
    "columns": {
        "granule_id":             {"type": "string",  "filterable": True,  "selectable": True},
        "campaign_name":          {"type": "string",  "filterable": True,  "selectable": True},
        "sensor_name":            {"type": "string",  "filterable": True,  "selectable": True},
        "acquisition_date":       {"type": "date",    "filterable": True,  "selectable": True},
        "acquisition_start_time": {"type": "string",  "filterable": False, "selectable": True},
        "cloudy_conditions":      {"type": "string",  "filterable": True,  "selectable": True},
        "cloud_type":             {"type": "string",  "filterable": True,  "selectable": True},
        "gsd":                    {"type": "numeric", "filterable": True,  "selectable": True},
        "flightline_id":          {"type": "string",  "filterable": True,  "selectable": True},
        "granule_rad_url":        {"type": "string",  "filterable": False, "selectable": True},
        "granule_refl_url":       {"type": "string",  "filterable": False, "selectable": True},
        "raster_epsg":            {"type": "numeric", "filterable": False, "selectable": True},
    },
},
```

### Update `extracted_spectra_view`

Add `acquisition_start_time` column (present in `views_v2.sql`, missing from the old
config):

```python
"acquisition_start_time": {"type": "string", "filterable": False, "selectable": True},
```

### Update `reflectance_view`

Add `acquisition_start_time` column:

```python
"acquisition_start_time": {"type": "string", "filterable": False, "selectable": True},
```

---

## `schema/grant.sql`

Add grants for the new v2 views and direct `pixel` table access (needed by Stage 2b
aggregation query in `orchestration.py`):

```sql
-- New v2 views
GRANT SELECT ON vswir_plants.plot_shape_view  TO postgrest_user;
GRANT SELECT ON vswir_plants.trait_view       TO postgrest_user;
GRANT SELECT ON vswir_plants.granule_view     TO postgrest_user;

-- pixel table needed for Stage 2b pixel aggregation
GRANT SELECT ON vswir_plants.pixel            TO postgrest_user;

-- Revoke old views no longer in use
REVOKE SELECT ON vswir_plants.plot_pixels_mv  FROM postgrest_user;
REVOKE SELECT ON vswir_plants.leaf_traits_view FROM postgrest_user;
```

The existing grants for `extracted_spectra_view`, `extracted_metadata_view`, and
`reflectance_view` remain unchanged.

---

## `terraform_deployment/modules/api/main.tf`

Update API Gateway routes:

- Remove `POST /views/{view_name}`
- Add `POST /query`
- Add `POST /query/{view_name}`
- Add `POST /query/spectra`
- Add `POST /query/reflectance`
- Add `GET /query/metadata`
