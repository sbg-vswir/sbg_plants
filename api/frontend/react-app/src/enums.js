// enums.js

export const taxa = Object.freeze([
  'Acomastylis rossii',
  'Agastache urticifolia',
  'Agrostis spp',
  'Alnus incana',
  'Anemone multifida',
  'Anemonastrum narcissiflorum',
  'Aquilegia coerulea',
  'Arnica mollis',
  'Arnica parryi',
  'Artemisia dracunculus',
  'Artemisia tridentata',
  'Populus tremuloides',
  'Bistorta bistortoides',
  'Betula glandulosa',
  'Salix boothii',
  'Salix brachycarpa',
  'Bromopsis inermis',
  'Calamagrostis stricta',
  'Carex aquatilis',
  'Carex hoodii',
  'Carex lenticularis',
  'Carex microptera',
  'Carex siccata',
  'Carex spp',
  'Carex utriculata',
  'Castilleja rhexiifolia',
  'Castilleja sulphurea',
  'Clementsia rhodantha',
  'Corydalis caseana',
  'Delphinium barbeyi',
  'Deschampsia cespitosa',
  'Distegia involucrata',
  'Salix drummondiana',
  'Dugaldia hoopesii',
  'Sambucus microbotrys',
  'Elymus lanceolatus',
  'Elymus spp',
  'Picea engelmannii',
  'Erigeron glacialis',
  'Erigeron speciosus',
  'Erythronium grandiflorum',
  'Eucephalus engelmannii',
  'Festuca idahoensis',
  'Festuca thurberi',
  'Festuca spp',
  'Chamerion danielsii',
  'Frasera speciosa',
  'Fragaria virgiana',
  'Galium boreale',
  'Geranium richardsonii',
  'Salix geyeriana',
  'Salix glauca',
  'Ribes montigenum',
  'Heliomeris multiflora',
  'Helianthella quinquenervis',
  'Heracleum maximum',
  'Heterotheca villosa',
  'Hydrophyllum fendleri',
  'Iris missouriensis',
  'Juncus arcticus',
  'Juniperus communis',
  'Lathyrus lanszwertii',
  'Ligusticum porteri',
  'Linum lewisii',
  'Pinus contorta',
  'Lupinus argenteus',
  'Lupinus bakeri',
  'Mertensia ciliata',
  'Mertensia lanceolata',
  'Osmorhiza occidentalis',
  'Pedicularis groenlandica',
  'Pentaphylloides floribunda',
  'Salix planifolia',
  'Poa compressa',
  'Poa leptocoma',
  'Poa secunda',
  'Potentilla pulcherrima',
  'Pseudocymopterus montanus',
  'Psychrophila leptosepala',
  'Pyrrocoma crocea',
  'Rubus idaeus',
  'Tolmachevia integrifolia',
  'Rumex densiflorus',
  'Senecio crassulus',
  'Senecio serra',
  'Senecio triangularis',
  'Sibbaldia procumbens',
  'Symphoricarpos rotundifolius',
  'Solidago spp',
  'Sorbus scopulina',
  'Abies lasiocarpa',
  'Symphyotrichum spp',
  'Thalictrum fendleri',
  'Vaccinium cespitosum',
  'Valeriana edulis',
  'Valeriana occidentalis',
  'Veratrum tenuipetalum',
  'Vicia americana',
  'Salix spp',
  'Salix wolfii',
  'Wyethia amplexicaulis',
  'Wyethia spp',
  'Not recorded'
]);

// export const ELEVATION_SOURCE = Object.freeze([
//   'NEON AOP Lidar',
//   'Copernicus 30m DEM'
// ]);

// export const EXTRACTION_METHOD = Object.freeze([
//   'Internal centroids',
//   'Full intersection',
//   'Buffer'
// ]);

export const veg_or_cover_type = Object.freeze([
  'Grass',
  'Forb',
  'Fern',
  'Low shrub',
  'Broadleaf',
  'Needleleaf',
  'Lichen',
  'Epiphyte or Hemiepiphyte',
  'Bare',
  'NPV',
  'Moss',
  'PV',
  'Water',
  'Herbaceous clip strip - NEON',
  'Woody individual'
]);

export const plant_status = Object.freeze([
  'Insect damaged',
  'Disease damaged',
  'Other damage',
  'Physically damaged',
  'Not recorded',
  'Flowering',
  'Fruit setting',
  'Fruiting'
]);

export const phenophase = Object.freeze([
  'Leaves fully expanded',
  'Leaves not fully expanded',
  'Leaves beginning to senesce',
  'Most leaves senesced',
  'Not recorded'
]);

export const plot_vegetation_type = Object.freeze([
  'Meadow',
  'Shrub',
  'Tree',
  'Grassland',
  'Not recorded'
]);

// export const DELINEATION_METHOD = Object.freeze([
//   'Posthoc',
//   'Radius Buffer',
//   'In Field'
// ]);

// export const CLOUD_CONDITIONS = Object.freeze([
//   'Red',
//   'Yellow',
//   'Green',
//   'Not recorded'
// ]);

// export const CLOUD_TYPE = Object.freeze([
//   'Cumulus - sun not obscured',
//   'Cirrus - sun obscured',
//   'Stratus',
//   'Cumulus',
//   'Cirrus',
//   'Haze',
//   'Clear Sky',
//   'Unknown cloud type',
//   'Cumulus / Cirrus',
//   'Cirrus - sun not obscured',
//   'Cumulus - sun obscured',
//   'Stratus - sun obscured',
//   'Stratus - sun not obscured',
//   'Cumulus / Clear',
//   'Cirrus / Clear',
//   'Complete stratus cover',
//   'Not Collected'
// ]);

// export const ERROR_TYPE = Object.freeze([
//   'Instrument precision',
//   'Standard deviation of measurement',
//   'Standard error of measurement'
// ]);

export const fractional_class = Object.freeze([
  'pv',
  'npv',
  'soil',
  'water',
  'char',
  'snow',
  'flowers',
  'seeds'
]);

export const subplot_cover_method = Object.freeze([
  'Point',
  'Line-intercept-transect',
  'Quadrat',
  'Visual assessment',
  'N/A'
]);

export const plot_method = Object.freeze([
  'Individual',
  'Transect',
  'Plot',
  'Clip strip'
]);

// export const REPOSITORY = Object.freeze([
//   'ORNL DAAC',
//   'NEON',
//   'ECOSIS',
//   'ESS-DIVE'
// ]);

export const handling = Object.freeze([
  'Fresh',
  'Flash frozen',
  'Oven dried'
]);

export const sensor_name = Object.freeze([
  'NEON AIS 1',
  'NEON AIS 2',
  'NEON AIS 3',
  'AVIRIS-Classic',
  'AVIRIS-NG',
  'AVIRIS-3',
  'AVIRIS-5'
]);

export const trait = Object.freeze([
  'wet weight',
  'dry weight',
  'LWC',
  'CRF',
  'Chl',
  'LMA',
  'LAI',
  'Nitrogen',
  'Phosphorus',
  'Magnesium',
  'Potassium',
  'Calcium',
  'Sulfur',
  'Boron',
  'Iron',
  'Manganese',
  'Copper',
  'Zinc',
  'Aluminum',
  'Sodium'
]);

export const trait_method = Object.freeze([
  'Chemical analysis',
  'Benchtop spectral PLSR',
  'Field measured (CCM)',
  'Weight based'
]);

// export const TRAIT_UNITS = Object.freeze([
//   'g',
//   'percentage',
//   'ratio',
//   'mg m-2',
//   'grams dry mass per g m2',
//   'concentration in percent dry mass',
//   'concentration in ppm'
// ]);