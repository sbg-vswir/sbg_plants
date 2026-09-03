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
    'not recorded'
); 

CREATE TYPE vswir_plants."CAMPAIGN_name" AS ENUM (
    'East River 2018'
);


-- should we add version to this???
CREATE TYPE vswir_plants."ELEVATION_source" AS ENUM (
    'NEON AOP Lidar',
    'Copernicus 30m DEM'
);

CREATE TYPE vswir_plants."EXTRACTION_method" AS ENUM (
   'internal centroids',
   'full intersection',
   'buffer'
); 

CREATE TYPE vswir_plants."VEG_or_cover_type" AS ENUM (
    'grass',
    'forb',
    'fern',
    'low shrub',
    'broadleaf',
    'needleleaf',
    'lichen',
    'epiphyte or hemiepiphyte',
    'bare',
    'npv',
    'moss',
    'pv',
    'water',
    'herbaceous clip strip - NEON',
    'woody individual',
    -- 'Herbaceous aggregate sample'
); 

CREATE TYPE vswir_plants."PLANT_status" AS ENUM (
    -- 'OK', from neon data?
    'insect damaged',
    'disease damaged',
    'other damage',
    'physically damaged',
    'not recorded',
    'flowering',
    'fruit setting',
    'fruiting'
); 


CREATE TYPE vswir_plants."PHENOPHASE" AS ENUM (
    'leaves fully expanded',
    'leaves not fully expanded',
    'leaves beginning to senesce',
    'most leaves senesced',
    'not recorded'
); 

CREATE TYPE vswir_plants."VEGETATION_type" AS ENUM (
   'meadow',
   'shrub',
   'tree',
   'grassland',
   'not recorded'
); 

CREATE TYPE vswir_plants."DELINEATION_method" AS ENUM (
    'posthoc',
    'radius buffer',
    'in field'
); 

CREATE TYPE vswir_plants."CLOUD_conditions" AS ENUM (
    'red', -- over 33%
    'yellow', -- 10 to 33%
    'green', -- less than 10%
    'not recorded'
); 

CREATE TYPE vswir_plants."CLOUD_type" AS ENUM (
    'cumulus - sun not obscured',
    'cirrus - sun obscured', 
    'stratus',
    'cumulus', 
    'cirrus', 
    'haze', 
    'clear sky', 
    'unknown cloud type', 
    'cumulus / cirrus', 
    'cirrus - sun not obscured', 
    'cumulus - sun obscured', 
    'stratus - sun obscured', 
    'stratus - sun not obscured', 
    'cumulus / clear', 
    'cirrus / clear', 
    'complete stratus cover',
    'not recorded'
); 

CREATE TYPE vswir_plants."Error_type" AS ENUM (
    'instrument precision',
    'standard deviation of measurement',
    'standard error of measurement'
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
    -- 'not recorded'
);

CREATE TYPE vswir_plants."SUBPLOT_cover_method" AS ENUM (
    'point',
    'line-intercept-transect',
    'quadrat',
    'visual assessment',
    'N/A'
    -- 'not recorded'
);

CREATE TYPE vswir_plants."PLOT_method" AS ENUM (
    'individual',
    'transect',
    'plot',
    'clip strip'
);


CREATE TYPE vswir_plants."Repository" AS ENUM (
    'ORNL DAAC',
    'NEON',
    'ECOSIS',
    'ESS-DIVE'
);

CREATE TYPE vswir_plants."Sample_handling" AS ENUM (
    'fresh',
    'flash frozen',
    'oven dried'
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
    'lwc',
    'crf',
    'chl',
    'lma',
    'lai',
    'nitrogen',
    'phosphorus',
    'magnesium',
    'potassium',
    'calcium',
    'sulfur',
    'boron',
    'iron',
    'manganese',
    'copper',
    'zinc',
    'aluminum',
    'sodium',
    'd13c',
    'carbon'
);

CREATE TYPE vswir_plants."Trait_method" AS ENUM (
    'chemical analysis',
    'benchtop spectral plsr',
    'field measured (ccm)', -- does this need (ccm)
    'weight based'
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

CREATE TYPE vswir_plants."CANOPY_position" AS ENUM (
    'partially shaded',
    'full sun',
    'mostly shaded',
    'open grown',
    'not recorded'
);
