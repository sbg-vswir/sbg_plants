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
| `pages/LinkedQueryPage.jsx` | Page layout |
| `hooks/useLinkedQuery.js` | All state — filters, response, selected plot, derived data |
| `components/LinkedFilterPanel.jsx` | Two-section filter panel (trait + granule filters) |
| `components/PlotSidePanel.jsx` | Slides in on map click — trait + granule summary for selected plot |
| `components/LinkedDataTable.jsx` | Two-tab table (Traits / Granules) with download buttons |

---

## Changed Files

| File | Change |
|---|---|
| `utils/api.js` | Add `fetchLinkedQuery()`. Update `fetchParquet()` to use `/query/{view_name}`. Update `extractSpectra()` to use `/query/spectra` and `/query/reflectance`. |
| `App.jsx` | Add `/linked-query` route + Navbar link |

---

## Unchanged Files

`QueryPage.jsx`, `IsoFitPage.jsx`, `useDataQuery.js`, `useQueryPage.js`,
`useSpectraExtraction.js`, `useIsoFitJob.js`, `MapView.jsx`, `FilterSection.jsx`,
`DataTable.jsx`, `helpers.js`

---

## Page Layout — `LinkedQueryPage.jsx`

```
┌─────────────────────────────────────────────────────────┐
│ Navbar                                                   │
├──────────────────────┬──────────────────────────────────┤
│ Filter Panel (380px) │ Map (flex-1)                      │
│   General filter     │                                   │
│   - campaign         ├──────────────────────────────────┤
│   Spatial filter     │ Side Panel (slides in on click)   │
│   - GeoJSON upload   │  Plot identity                    │
│                      │  Traits for this plot             │
│  Trait filters       │  Granules for this plot           │
│  - trait             │  Extract Spectra button           │
│  - taxa              ├──────────────────────────────────┤
│  - veg/cover type    │ Table (two tabs)                  │
│  - phenophase        │  [ Traits ] [ Granules ]          │
│  - plant status      │  Download buttons per tab         │
│  - canopy position   │                                   │
│  - sample_fc_class   │                                   │
│  - handling / method │                                   │
│  - collection date   │                                   │
│                      │                                   │
│  Granule filters     │                                   │
│  - sensor            │                                   │
│  - cloudy conditions │                                   │
│  - cloud type        │                                   │
│  - acquisition date  │                                   │
│                      │                                   │
│  [ Apply ] [ Reset ] │                                   │
│  ⚠ truncated warning │                                   │
└──────────────────────┴──────────────────────────────────┘
```

---

## `hooks/useLinkedQuery.js`

Owns all state for the linked query. Key responsibilities:

**Filter state:**
- `geojsonContent` — uploaded GeoJSON string
- `traitFilters` — object of trait filter values
- `granuleFilters` — object of granule filter values

**Response state:**
- `plots`, `traits`, `granules` — arrays from API response
- `truncated` — bool
- `plotCount`, `traitCount`, `granuleCount` — counts in response
- `totalPlotCount`, `totalTraitCount`, `totalGranuleCount` — total counts before limit
- `loading`, `error`

**Selected plot state:**
- `selectedPlotId` — plot_id of clicked map feature
- `selectedTraits` — derived: `traits.filter(t => t.plot_id === selectedPlotId)`
- `selectedGranules` — derived: `granules.filter(g => g.plot_ids.includes(selectedPlotId))`

**`getPixelRanges()`** — same contract as `useDataQuery.getPixelRanges()`:
- Extracts `pixel_ids` from `granules` array
- Groups by `campaign_name|sensor_name`
- Applies `toRanges()` from `helpers.js`
- Returns `{ "campaign|sensor": [[start, end], ...] }`
- Allows `useSpectraExtraction` and `useIsoFitJob` to be reused without modification

**`handleApply()`** — calls `fetchLinkedQuery()` from `utils/api.js` with assembled
filters, updates all response state.

---

## `utils/api.js` Changes

### Add `fetchLinkedQuery(payload)`

```js
export async function fetchLinkedQuery(payload) {
    const response = await client.post('/query', payload);
    return response.data;
}
```

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

## Extract Spectra Flow

The Extract Spectra and Run ISOFIT buttons on `LinkedQueryPage` work identically to
`QueryPage` — `useSpectraExtraction` and `useIsoFitJob` are passed `getPixelRanges`
from `useLinkedQuery`, which has the same contract as `useDataQuery.getPixelRanges`.
No changes to either hook.
