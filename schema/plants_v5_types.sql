CREATE TYPE vswir_plants."TAXA" AS ENUM (
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
); 


-- should we add version to this???
CREATE TYPE vswir_plants."ELEVATION_source" AS ENUM (
    'NEON AOP Lidar',
    'Copernicus 30m DEM'
);

CREATE TYPE vswir_plants."EXTRACTION_method" AS ENUM (
   'Internal centroids',
   'Full intersection',
   'Buffer'
); 

CREATE TYPE vswir_plants."VEG_or_cover_type" AS ENUM (
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
); 

CREATE TYPE vswir_plants."PLANT_status" AS ENUM (
    -- 'OK',
    'Insect damaged',
    'Disease damaged',
    'Other damage',
    'Physically damaged',
    'Not recorded',
    'Flowering',
    'Fruit setting',
    'Fruiting'
); 


CREATE TYPE vswir_plants."PHENOPHASE" AS ENUM (
    'Leaves fully expanded',
    'Leaves not fully expanded',
    'Leaves beginning to senesce',
    'Most leaves senesced',
    'Not recorded'
); 

CREATE TYPE vswir_plants."VEGETATION_type" AS ENUM (
   'Meadow',
   'Shrub',
   'Tree',
   'Grassland'
   'Not recorded'
); 

CREATE TYPE vswir_plants."DELINEATION_method" AS ENUM (
    'Posthoc',
    'Radius Buffer',
    'In Field'
); 

CREATE TYPE vswir_plants."CLOUD_conditions" AS ENUM (
    'Red',
    'Yellow',
    'Green',
    'Not recorded'
); 

CREATE TYPE vswir_plants."CLOUD_type" AS ENUM (
    'Cumulus - sun not obscured',
    'Cirrus - sun obscured', 
    'Stratus',
    'Cumulus', 
    'Cirrus', 
    'Haze', 
    'Clear Sky', 
    'Unknown cloud type', 
    'Cumulus / Cirrus', 
    'Cirrus - sun not obscured', 
    'Cumulus - sun obscured', 
    'Stratus - sun obscured', 
    'Stratus - sun not obscured', 
    'Cumulus / Clear', 
    'Cirrus / Clear', 
    'Complete stratus cover',
    'Not Collected'
); 

CREATE TYPE vswir_plants."Error_type" AS ENUM (
    'Instrument precision',
    'Standard deviation of measurement',
    'Standard error of measurement'
);

CREATE TYPE vswir_plants."FRACTIONAL_class" AS ENUM (
    'pv',
    'npv',
    'soil',
    'water',
    'char',
    'snow',
    'flowers',
    'seeds'
);

CREATE TYPE vswir_plants."SUBPLOT_cover_method" AS ENUM (
    'Point',
    'Line-intercept-transect',
    'Quadrat',
    'Visual assessment',
    'N/A'
);

CREATE TYPE vswir_plants."PLOT_method" AS ENUM (
    'Individual',
    'Transect',
    'Plot',
    'Clip strip'
);


CREATE TYPE vswir_plants."Repository" AS ENUM (
    'ORNL DAAC',
    'NEON',
    'ECOSIS',
    'ESS-DIVE'
);

CREATE TYPE vswir_plants."Sample_handling" AS ENUM (
    'Fresh',
    'Flash frozen',
    'Oven dried'
);

CREATE TYPE vswir_plants."Sensor_name" AS ENUM (
    'NEON AIS 1',
    'NEON AIS 2',
    'NEON AIS 3',
    'AVIRIS-Classic',
    'AVIRIS-NG',
    'AVIRIS-3',
    'AVIRIS-5'
);

CREATE TYPE vswir_plants."Trait" AS ENUM (
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
);

CREATE TYPE vswir_plants."Trait_method" AS ENUM (
    'Chemical analysis',
    'Benchtop spectral PLSR',
    'Field measured (CCM)',
    'Weight based'
);

CREATE TYPE vswir_plants."Trait_units" AS ENUM (
    'g',
    'percentage',
    'ratio',
    'mg m-2',
    'grams dry mass per g m2',
    'concentration in percent dry mass',
    'concentration in ppm'
);
