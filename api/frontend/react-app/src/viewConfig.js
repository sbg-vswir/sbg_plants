// ============================================================================
// viewConfig.js — single source of truth for all frontend view configuration.
//
// To add a new view:
//   1. Add its columns to ENUMS if it has new enum fields
//   2. Add one entry to VIEW_CONFIG with filters and select
//
// Filter types: "text" | "date" | "enum"
// Enum filters must include an `options` array.
// ============================================================================

// ---------------------------------------------------------------------------
// Shared enum option lists
// ---------------------------------------------------------------------------

export const ENUMS = {
  sensor_name: [
    'NEON AIS 1',
    'NEON AIS 2',
    'NEON AIS 3',
    'AVIRIS-Classic',
    'AVIRIS-NG',
    'AVIRIS-3',
    'AVIRIS-5',
  ],

  taxa: [
    'Acomastylis rossii', 'Agastache urticifolia', 'Agrostis spp',
    'Alnus incana', 'Anemone multifida', 'Anemonastrum narcissiflorum',
    'Aquilegia coerulea', 'Arnica mollis', 'Arnica parryi',
    'Artemisia dracunculus', 'Artemisia tridentata', 'Populus tremuloides',
    'Bistorta bistortoides', 'Betula glandulosa', 'Salix boothii',
    'Salix brachycarpa', 'Bromopsis inermis', 'Calamagrostis stricta',
    'Carex aquatilis', 'Carex hoodii', 'Carex lenticularis',
    'Carex microptera', 'Carex siccata', 'Carex spp', 'Carex utriculata',
    'Castilleja rhexiifolia', 'Castilleja sulphurea', 'Clementsia rhodantha',
    'Corydalis caseana', 'Delphinium barbeyi', 'Deschampsia cespitosa',
    'Distegia involucrata', 'Salix drummondiana', 'Dugaldia hoopesii',
    'Sambucus microbotrys', 'Elymus lanceolatus', 'Elymus spp',
    'Picea engelmannii', 'Erigeron glacialis', 'Erigeron speciosus',
    'Erythronium grandiflorum', 'Eucephalus engelmannii', 'Festuca idahoensis',
    'Festuca thurberi', 'Festuca spp', 'Chamerion danielsii',
    'Frasera speciosa', 'Fragaria virgiana', 'Galium boreale',
    'Geranium richardsonii', 'Salix geyeriana', 'Salix glauca',
    'Ribes montigenum', 'Heliomeris multiflora', 'Helianthella quinquenervis',
    'Heracleum maximum', 'Heterotheca villosa', 'Hydrophyllum fendleri',
    'Iris missouriensis', 'Juncus arcticus', 'Juniperus communis',
    'Lathyrus lanszwertii', 'Ligusticum porteri', 'Linum lewisii',
    'Pinus contorta', 'Lupinus argenteus', 'Lupinus bakeri',
    'Mertensia ciliata', 'Mertensia lanceolata', 'Osmorhiza occidentalis',
    'Pedicularis groenlandica', 'Pentaphylloides floribunda', 'Salix planifolia',
    'Poa compressa', 'Poa leptocoma', 'Poa secunda', 'Potentilla pulcherrima',
    'Pseudocymopterus montanus', 'Psychrophila leptosepala', 'Pyrrocoma crocea',
    'Rubus idaeus', 'Tolmachevia integrifolia', 'Rumex densiflorus',
    'Senecio crassulus', 'Senecio serra', 'Senecio triangularis',
    'Sibbaldia procumbens', 'Symphoricarpos rotundifolius', 'Solidago spp',
    'Sorbus scopulina', 'Abies lasiocarpa', 'Symphyotrichum spp',
    'Thalictrum fendleri', 'Vaccinium cespitosum', 'Valeriana edulis',
    'Valeriana occidentalis', 'Veratrum tenuipetalum', 'Vicia americana',
    'Salix spp', 'Salix wolfii', 'Wyethia amplexicaulis', 'Wyethia spp',
    'Not recorded',
  ],

  veg_or_cover_type: [
    'Grass', 'Forb', 'Fern', 'Low shrub', 'Broadleaf', 'Needleleaf',
    'Lichen', 'Epiphyte or Hemiepiphyte', 'Bare', 'NPV', 'Moss', 'PV',
    'Water', 'Herbaceous clip strip - NEON', 'Woody individual',
  ],

  canopy_position: [
    'Partially shaded',
    'Full sun',
    'Mostly shaded',
    'Open grown',
    'Not recorded',
  ],

  plant_status: [
    'Insect damaged', 'Disease damaged', 'Other damage', 'Physically damaged',
    'Not recorded', 'Flowering', 'Fruit setting', 'Fruiting',
  ],

  phenophase: [
    'Leaves fully expanded', 'Leaves not fully expanded',
    'Leaves beginning to senesce', 'Most leaves senesced', 'Not recorded',
  ],

  plot_veg_type: [
    'Meadow', 'Shrub', 'Tree', 'Grassland', 'Not recorded',
  ],

  sample_fc_class: [
    'pv', 'npv', 'soil', 'water', 'char', 'snow', 'flowers', 'seeds',
  ],

  subplot_cover_method: [
    'Point', 'Line-intercept-transect', 'Quadrat', 'Visual assessment', 'N/A',
  ],

  plot_method: [
    'Individual', 'Transect', 'Plot', 'Clip strip',
  ],

  cloudy_conditions: [
    'Red', 'Yellow', 'Green', 'Not recorded',
  ],

  cloud_type: [
    'Clear Sky', 'Haze', 'Cirrus', 'Cirrus - sun not obscured', 'Cirrus - sun obscured',
    'Cirrus / Clear', 'Cumulus', 'Cumulus - sun not obscured', 'Cumulus - sun obscured',
    'Cumulus / Clear', 'Cumulus / Cirrus', 'Stratus', 'Stratus - sun not obscured',
    'Stratus - sun obscured', 'Complete stratus cover', 'Unknown cloud type', 'Not collected',
  ],

  extraction_method: [
    'Internal centroids', 'Full intersection', 'Buffer',
  ],

  delineation_method: [
    'Posthoc', 'Radius Buffer', 'In Field',
  ],

  handling: [
    'Fresh', 'Flash frozen', 'Oven dried',
  ],

  trait: [
    'wet weight', 'dry weight', 'LWC', 'CRF', 'Chl', 'LMA', 'LAI',
    'Nitrogen', 'Phosphorus', 'Magnesium', 'Potassium', 'Calcium',
    'Sulfur', 'Boron', 'Iron', 'Manganese', 'Copper', 'Zinc',
    'Aluminum', 'Sodium',
  ],

  trait_method: [
    'Chemical analysis', 'Benchtop spectral PLSR',
    'Field measured (CCM)', 'Weight based',
  ],
};

// ---------------------------------------------------------------------------
// View config — filters and selectable columns per view
// ---------------------------------------------------------------------------

export const VIEW_CONFIG = {
  plot_shape_view: {
    queryable: true,
    displayName: 'Plots',
    hideExtract: false,
    filters: [
      { id: 'plot_name',     label: 'Plot Name:',     type: 'text', placeholder: 'e.g., 276-ER18,001-ER18' },
      { id: 'campaign_name', label: 'Campaign Name:', type: 'text', placeholder: 'e.g., East River 2018' },
      { id: 'site_id',       label: 'Site ID:',       type: 'text', placeholder: 'e.g., CRBU' },
      { id: 'plot_method',   label: 'Plot Method:',   type: 'enum', options: ENUMS.plot_method },
    ],
    select: [
      'plot_id', 'campaign_name', 'site_id', 'plot_name', 'plot_method', 'plot_shape_id', 'geom',
    ],
  },

  trait_view: {
    queryable: true,
    displayName: 'Traits',
    hideExtract: true,
    filters: [
      { id: 'campaign_name',       label: 'Campaign Name:',       type: 'text', placeholder: 'e.g., East River 2018' },
      { id: 'site_id',             label: 'Site ID:',             type: 'text', placeholder: 'e.g., CRBU' },
      { id: 'plot_name',           label: 'Plot Name:',           type: 'text', placeholder: 'e.g., 276-ER18,001-ER18' },
      { id: 'sample_name',         label: 'Sample Name:',         type: 'text', placeholder: 'e.g., 021-ER18_Salixwolfii' },
      { id: 'trait',               label: 'Trait:',               type: 'enum', options: ENUMS.trait },
      { id: 'taxa',                label: 'Taxa:',                type: 'enum', options: ENUMS.taxa },
      { id: 'veg_or_cover_type',   label: 'Vegetation/Cover Type:', type: 'enum', options: ENUMS.veg_or_cover_type },
      { id: 'phenophase',          label: 'Phenophase:',          type: 'enum', options: ENUMS.phenophase },
      { id: 'plant_status',        label: 'Plant Status:',        type: 'enum', options: ENUMS.plant_status },
      { id: 'canopy_position',     label: 'Canopy Position:',     type: 'enum', options: ENUMS.canopy_position },
      { id: 'plot_veg_type',       label: 'Plot Vegetation Type:', type: 'enum', options: ENUMS.plot_veg_type },
      { id: 'subplot_cover_method', label: 'Subplot Cover Method:', type: 'enum', options: ENUMS.subplot_cover_method },
      { id: 'sample_fc_class',     label: 'Fractional Class:',    type: 'enum', options: ENUMS.sample_fc_class },
      { id: 'handling',            label: 'Sample Handling:',     type: 'enum', options: ENUMS.handling },
      { id: 'plot_method',         label: 'Plot Method:',         type: 'enum', options: ENUMS.plot_method },
      { id: 'method',              label: 'Trait Method:',        type: 'enum', options: ENUMS.trait_method },
      { id: 'start_date',          label: 'Start Date:',          type: 'date' },
      { id: 'end_date',            label: 'End Date:',            type: 'date' },
    ],
    select: [
      'campaign_name', 'plot_id', 'site_id', 'plot_name', 'sample_name', 'collection_date',
      'trait', 'value', 'units', 'method', 'handling', 'error', 'error_type',
      'taxa', 'veg_or_cover_type', 'phenophase', 'sample_fc_class',
      'canopy_position', 'plant_status', 'plot_veg_type', 'subplot_cover_method',
      'floristic_survey', 'plot_method',
    ],
  },

  granule_view: {
    queryable: true,
    displayName: 'Granules',
    hideExtract: false,
    filters: [
      { id: 'campaign_name',    label: 'Campaign Name:',    type: 'text', placeholder: 'e.g., East River 2018' },
      { id: 'sensor_name',      label: 'Sensor Name:',      type: 'enum', options: ENUMS.sensor_name },
      { id: 'cloudy_conditions', label: 'Cloud Conditions:', type: 'enum', options: ENUMS.cloudy_conditions },
      { id: 'cloud_type',       label: 'Cloud Type:',       type: 'enum', options: ENUMS.cloud_type },
      { id: 'start_date',       label: 'Start Date:',       type: 'date' },
      { id: 'end_date',         label: 'End Date:',         type: 'date' },
    ],
    select: [
      'granule_id', 'campaign_name', 'sensor_name', 'acquisition_date',
      'acquisition_start_time', 'cloudy_conditions', 'cloud_type', 'gsd',
    ],
  },

  extracted_spectra_view: {
    queryable: false,
    filters: [],
    select: ['pixel_id', 'campaign_name', 'sensor_name', 'granule_id', 'plot_id', 'plot_name', 'shade_mask'],
  },

  reflectance_view: {
    queryable: false,
    filters: [],
    select: ['pixel_id', 'campaign_name', 'sensor_name', 'granule_id', 'plot_id', 'plot_name', 'lon', 'lat', 'elevation', 'cloudy_conditions', 'cloud_type'],
  },

  extracted_metadata_view: {
    queryable: false,
    filters: [],
    select: ['wavelength_center', 'fwhm'],
  },
};

// ---------------------------------------------------------------------------
// Helpers — keep callers simple
// ---------------------------------------------------------------------------

// All view names (including internal ones — used by api.js)
export const ALL_VIEWS = Object.keys(VIEW_CONFIG);

// Only views that are user-queryable — used by the view selector in the Navbar
export const VIEWS = Object.keys(VIEW_CONFIG).filter(k => VIEW_CONFIG[k].queryable);

// Filter definitions for a view
export const getFilters = (viewName) =>
  VIEW_CONFIG[viewName]?.filters ?? [];

// Selectable columns for a view — consumed by api.js fetchParquet
export const SELECT_CONFIGS = Object.fromEntries(
  Object.entries(VIEW_CONFIG).map(([k, v]) => [k, v.select])
);

// Legacy alias — VIEW_CONFIGS was used in pages for the filters array
// Only exposes queryable views so the view selector stays clean
export const VIEW_CONFIGS = Object.fromEntries(
  Object.entries(VIEW_CONFIG)
    .filter(([, v]) => v.queryable)
    .map(([k, v]) => [k, { filters: v.filters }])
);
