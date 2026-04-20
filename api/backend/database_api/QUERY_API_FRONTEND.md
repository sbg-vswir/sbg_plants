# `/query` API — Frontend Implementation Plan

## Overview

The new linked query feature is implemented as a new page `LinkedQueryPage`. Existing
pages (`QueryPage`, `IsoFitPage`) are untouched. The existing single-view query flow
continues to work through `POST /query/{view_name}` — only the route path changes in
`utils/api.js`.

---

## New Files

| File | Description |
|---|---|
| `pages/LinkedQueryPage.jsx` | Page layout — composes all linked query components |
| `hooks/useLinkedQuery.js` | All state — filters, response, pagination, selected plot, derived data |
| `components/LinkedFilterPanel.jsx` | Filter panel: campaign (top-level), trait filters, granule filters |
| `components/PlotSidePanel.jsx` | Slides in on map plot click — trait and granule summary for selected plot |
| `components/LinkedDataTable.jsx` | Two-tab table (Traits / Granules) for all displayed plots |

---

## Changed Files

| File | Change |
|---|---|
| `utils/api.js` | Add `fetchLinkedQuery()`. Update `fetchParquet()` to `/query/{view_name}`. Update `extractSpectra()` to `/query/spectra` and `/query/reflectance`. |
| `App.jsx` | Add `/linked-query` route + Navbar link |
| `components/MapView.jsx` | Add draw tool support. Add per-feature click handler prop. |

---

## Unchanged Files

`QueryPage.jsx`, `IsoFitPage.jsx`, `useDataQuery.js`, `useQueryPage.js`,
`useSpectraExtraction.js`, `useIsoFitJob.js`, `FilterSection.jsx`,
`DataTable.jsx`, `helpers.js`

---

## Page Layout — `LinkedQueryPage.jsx`

```
┌──────────────────────────────────────────────────────────────┐
│ Navbar                                                        │
├──────────────────────┬───────────────────────────────────────┤
│ Filter Panel (380px) │ Map (flex-1)                           │
│                      │  [ Draw ] [ Upload GeoJSON ] toolbar  │
│  Campaign            │                                        │
│  - campaign_name     │  Plot polygons rendered on map.        │
│                      │  Drawn/uploaded boundary shown as      │
│  Trait Filters       │  overlay. Clicking a plot polygon      │
│  - trait             │  opens the side panel.                 │
│  - taxa              │                                        │
│  - veg/cover type    ├───────────────────────────────────────┤
│  - phenophase        │ Side Panel (slides in on plot click)   │
│  - plant status      │  Plot: 020-ER18 · East River 2018     │
│  - canopy position   │                                        │
│  - sample_fc_class   │  Traits                                │
│  - handling          │  collection_date | trait | value | ... │
│  - method            │                                        │
│  - collection date   │  Granules                              │
│                      │  acq_date | sensor | pixel ranges      │
│  Granule Filters     │                                        │
│  - sensor            ├───────────────────────────────────────┤
│  - cloudy conditions │ Data Table                             │
│  - cloud type        │  [ Traits ] [ Granules ]               │
│  - acquisition date  │  Plots 1–100 of 1,247  [ < ] [ > ]    │
│                      │  All trait/granule rows for this page  │
│  [ Apply ] [ Reset ] │                                        │
│                      │  [ Extract Spectra ] [ Run ISOFIT ]    │
│  Plots: 100 of 1,247 │  [ Download merged CSV ]               │
│  [ < Prev ] [ Next > ]│                                        │
└──────────────────────┴───────────────────────────────────────┘
```

Pagination controls and result counts appear at the bottom of the filter panel. The
Extract Spectra, Run ISOFIT, and Download buttons are below the data table.

---

## `hooks/useLinkedQuery.js`

Owns all state for the linked query page. Key responsibilities:

### Filter state
- `campaignName` — string, top-level filter applied to all stages
- `geojsonContent` — GeoJSON object from draw tool or file upload
- `traitFilters` — object of trait filter values (trait, taxa, dates, etc.)
- `granuleFilters` — object of granule filter values (sensor, cloud, dates, etc.)

### Pagination state
- `offset` — current page offset, reset to `0` on Apply
- `limit` — plots per page, default `100`

### Response state
- `plots` — GeoJSON FeatureCollection (or array of plot objects)
- `traits` — array of trait row objects
- `granules` — array of granule objects (each with `plot_ids`, `pixel_ids` arrays)
- `truncated` — bool
- `plotCount`, `traitCount`, `granuleCount` — counts in current page
- `totalPlotCount`, `totalTraitCount`, `totalGranuleCount` — total counts before limit
- `loading`, `error`

### Selected plot state
- `selectedPlotId` — `plot_id` of the clicked map feature, `null` when panel closed
- `selectedTraits` — derived: `traits.filter(t => t.plot_id === selectedPlotId)`
- `selectedGranules` — derived: `granules.filter(g => g.plot_ids.includes(selectedPlotId))`

### Pagination actions
- `handleNext()` — increments `offset` by `limit`, calls API, clears `selectedPlotId`
- `handlePrev()` — decrements `offset` by `limit` (min 0), calls API, clears `selectedPlotId`
- `handleApply()` — resets `offset` to `0`, clears `selectedPlotId`, calls API

On page navigation the map, side panel, and table all update to match the new page of
plots. The side panel closes (selected plot cleared) when the page changes.

### `getPixelRanges()`

Same contract as `useDataQuery.getPixelRanges()` — allows `useSpectraExtraction` and
`useIsoFitJob` to be reused without modification:

```js
function getPixelRanges() {
    // granules: [{ granule_id, campaign_name, sensor_name, pixel_ids: [...], ... }]
    const grouped = {};
    for (const granule of granules) {
        const key = `${granule.campaign_name}|${granule.sensor_name}`;
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(...granule.pixel_ids);
    }
    const result = {};
    for (const [key, ids] of Object.entries(grouped)) {
        result[key] = toRanges(ids);  // toRanges from helpers.js
    }
    return result;
}
```

Extract Spectra operates on **all granules for all currently displayed plots** — not
just the selected plot. The side panel is informational only.

### `getMergedDownloadData()`

Produces the merged (pixel × trait) dataset for client-side CSV download, mirroring
the Python/R code examples:

```js
function getMergedDownloadData() {
    // Explode pixel_ids — one row per (granule, pixel)
    const pixelRows = granules.flatMap(g =>
        g.pixel_ids.map(pid => ({
            pixel_id: pid,
            granule_id: g.granule_id,
            sensor_name: g.sensor_name,
            acquisition_date: g.acquisition_date,
        }))
    );

    // Explode plot_ids — one row per (granule, plot)
    const granulePlotRows = granules.flatMap(g =>
        g.plot_ids.map(pid => ({ granule_id: g.granule_id, plot_id: pid }))
    );

    // Join traits via plot_id, then join spectra pixels via granule_id
    // Returns rows of: pixel_id, granule_id, sensor_name, acquisition_date,
    //                  plot_id, sample_name, trait, value, units, taxa, ...
    return pixelRows
        .flatMap(pr => {
            const gPlots = granulePlotRows.filter(gp => gp.granule_id === pr.granule_id);
            return gPlots.flatMap(gp => {
                const plotTraits = traits.filter(t => t.plot_id === gp.plot_id);
                return plotTraits.map(t => ({ ...pr, ...t }));
            });
        });
}
```

This runs entirely in the browser on already-fetched data — no additional API call.
The result is serialised to CSV using `convertToCSV` from `helpers.js`.

---

## `components/MapView.jsx` — Changes

Two new optional props, both defaulting to `undefined` so existing `QueryPage` usage
is unaffected:

### `onFeatureClick(plotId)`

Called when a rendered plot polygon is clicked. `LinkedQueryPage` passes a handler that
sets `selectedPlotId` in `useLinkedQuery`. The clicked feature is highlighted (e.g.
different fill colour/opacity).

```jsx
// Inside MapView — GeoJSON layer for linked query results:
<GeoJSON
    data={mapData}
    onEachFeature={(feature, layer) => {
        if (onFeatureClick) {
            layer.on('click', () => onFeatureClick(feature.properties.plot_id));
        }
    }}
    style={feature => ({
        fillColor: feature.properties.plot_id === selectedPlotId ? '#ff7800' : '#3388ff',
        fillOpacity: 0.4,
        weight: 1,
    })}
/>
```

A `selectedPlotId` prop is also added so MapView can highlight the selected feature
without needing to manage that state itself.

### `onShapeDrawn(geojson)`

Called when the user finishes drawing a polygon on the map. `LinkedQueryPage` passes
a handler that updates `geojsonContent` in `useLinkedQuery`.

Integrates Leaflet Draw (via `react-leaflet-draw` or equivalent). A small toolbar
appears on the map with Draw Polygon and Clear Shape controls. The drawn shape is
rendered as an overlay distinct from the plot polygons.

A GeoJSON file upload button is also provided in the map toolbar as an alternative to
drawing. Both the draw tool and upload set the same `geojsonContent` state — they are
mutually exclusive (uploading a file clears any drawn shape and vice versa).

---

## `components/PlotSidePanel.jsx`

Slides in from the right side of the map when a plot polygon is clicked. Closes when
the user clicks elsewhere on the map or clicks a close button.

**Contents:**
- Plot identity: `plot_name`, `campaign_name`, `site_id`
- **Traits table**: one row per trait measurement for the selected plot.
  Columns: `collection_date`, `trait`, `value`, `units`, `taxa`
- **Granules table**: one row per granule intersecting the selected plot.
  Columns: `acquisition_date`, `sensor_name`, abbreviated pixel ranges
  (e.g. `3817–3820, 4100–4102` — computed via `toRanges` from `helpers.js`)

The side panel is read-only. Extract Spectra and Download are page-level actions, not
per-plot actions.

---

## `components/LinkedDataTable.jsx`

Shows all trait and granule data for the **currently displayed page** of plots (not
just the selected plot). Two tabs:

- **Traits tab** — all rows from `traits` array for the current page
- **Granules tab** — all rows from `granules` array for the current page, with
  `plot_ids` and `pixel_ids` shown as abbreviated ranges

No per-tab download buttons. The Download action is a page-level button that triggers
`getMergedDownloadData()` → CSV.

---

## `utils/api.js` Changes

### Add `fetchLinkedQuery(payload)`

```js
export async function fetchLinkedQuery(payload) {
    const response = await client.post('/query', payload);
    return response.data;
}
```

Payload shape mirrors the `POST /query` request body — `campaign_name`, `geojson`,
`trait_filters`, `granule_filters`, `limit`, `offset`, `format`.

### Update `fetchParquet()`

```js
// was:  client.post(`/views/${view}`, ...)
// now:  client.post(`/query/${view}`, ...)
```

### Update `extractSpectra()`

```js
// was:
const view = spectraType === 'reflectance' ? 'reflectance_view' : 'extracted_spectra_view';
const url  = `/views/${view}`;

// now:
const url = spectraType === 'reflectance' ? '/query/reflectance' : '/query/spectra';
```

---

## Extract Spectra and ISOFIT Flow

The Extract Spectra and Run ISOFIT buttons on `LinkedQueryPage` work identically to
`QueryPage`. `useSpectraExtraction` and `useIsoFitJob` are passed `getPixelRanges`
from `useLinkedQuery`, which satisfies the same contract as `useDataQuery.getPixelRanges`.
No changes to either hook.

Both buttons operate on all granules for all plots on the current page. They are not
per-plot operations.

---

## Pagination UX

Pagination controls live at the bottom of the filter panel:

```
Plots: 100 of 1,247
[ < Prev ]  [ Next > ]
```

- **Apply** resets to page 1 (offset 0). Map, side panel, and table are cleared and
  repopulated with the first page of results.
- **Next / Prev** fetch the next/previous page. Map, side panel (closed), and table
  are replaced with the new page's data. Previous and next buttons are disabled at the
  first and last pages respectively.
- `total_plot_count`, `total_trait_count`, `total_granule_count` from the API response
  are used for the counts display — no separate count query is needed.
- If `truncated` is `false` (all results fit within the limit), no pagination controls
  are shown.
