CREATE TYPE vswir_plants."CAMPAIGN_name" AS ENUM (
    'East River 2018',
    'Colorado Headwaters Ecological Spectroscopy Study',
    'SHIFT'
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
    'herbaceous aggregate sample'
); 

CREATE TYPE vswir_plants."PLANT_status" AS ENUM (
    'insect damaged',
    'disease damaged',
    'other damage',
    'physically damaged',
    'flowering',
    'fruit setting',
    'fruiting',
    'not recorded'
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
   'wetland',
   'not recorded'
); 

CREATE TYPE vswir_plants."DELINEATION_method" AS ENUM (
    'posthoc',
    'radius buffer',
    'in field'
); 

CREATE TYPE vswir_plants."CLOUD_conditions" AS ENUM (
    'over 33%',
    '10 to 33%',
    'less than 10%',
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
    'seeds',
    'rock',
    'not recorded'
);

CREATE TYPE vswir_plants."SUBPLOT_cover_method" AS ENUM (
    'point',
    'line-intercept-transect',
    'quadrat',
    'visual assessment',
    'N/A'
    'not recorded'
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
    'ESS-DIVE',
    'NASA EarthData'
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
    'cfr',
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
    'd13C',
    'carbon'
);

CREATE TYPE vswir_plants."Trait_method" AS ENUM (
    'chemical analysis',
    'benchtop spectral plsr',
    'field measured',
    'weight based'
);

CREATE TYPE vswir_plants."Trait_units" AS ENUM (
    'g',
    'percentage',
    'ratio',
    'mg m-2',
    'grams dry mass per g m2',
    'concentration in percent dry mass',
    'concentration in ppm',
    'permil'
);

CREATE TYPE vswir_plants."CANOPY_position" AS ENUM (
    'partially shaded',
    'full sun',
    'mostly shaded',
    'open grown',
    'not recorded'
);

CREATE TYPE vswir_plants."POLYGON_confidence" AS ENUM (
    'high',
    'medium',
    'low',
    'not recorded'
);

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
    'Amelanchier alnifolia',
    'Juniperus scopulorum',
    'Ribes cereum',
    'Purshia tridentata',
    'Acer glabrum',
    'Salix monticola',
    'Holodiscus discolor',
    'Dasiphora fruticosa',
    'Lonicera involucrata',
    'Prunus virginiana',
    'Salix scouleriana',
    'Sambucus racemosa',
    'Ribes inerme',
    'Ribes wolfii',
    'Artemisia cana',
    'Cornus sericea',
    'Pseudotsuga menziessii',
    'Pinus ponderosa',
    'Pinus flexilis',
    'Populus angustifolia',
    'Brassica nigra',
    'Silybum marianum',
    'Erodium moschatum',
    'Quercus agrifolia',
    'Avena barbata',
    'Amsinckia menziesii',
    'Bromus diandrus',
    'Avena fatua',
    'Ramalina menziesii',
    'Quercus douglasii',
    'Eschscholzia californica',
    'Salvia leucophylla',
    'Artemisia californica',
    'Calandrinia menzieszii',
    'Lupinus nanus',
    'Quercus wislizeni',
    'Erodium cicutarium',
    'Centaurea melitensis',
    'Stipa pulchra',
    'Frangula californica',
    'Rhamnus crocea',
    'Acmispon glaber',
    'Erodium sp',
    'Hazardia squarrosa',
    'Medicago polymorpha',
    'Pinus sabiniana',
    'Bromus tectorum',
    'Eriodictyon tomentosum',
    'Pinus coulteri',
    'Ceanothus cuneatus',
    'Quercus lobata',
    'Salix lasiolepis',
    'Notholithocarpus densiflorus',
    'Adenostoma fasciculatum',
    'Eriogonum fasciculatum',
    'Hesperoyucca whipplei',
    'Rhus integrifolia',
    'Baccharis pilularis',
    'Hesperocyparis macrocarpa',
    'Elymus condensatus',
    'Phoradendron leucarpum',
    'Toxicoscordion fremontii',
    'Encelia californica',
    'Populus trichocarpa',
    'Leptosyne gigantea',
    'Carpobrotus edulis',
    'Croton setiger',
    'Lepidium nitidum',
    'Plantago erecta',
    'Calystegia macrostegia',
    'Schinus molle',
    'Eriogonum elonongatum',
    'Mimulus aurantiacus',
    'Arctostaphylos purissima',
    'Sambucus nigra',
    'Acacia pycnantha',
    'Thysanocarpus laciniatus',
    'Sisyrinchium bellum',
    'Arctostaphylos glandulosa',
    'Lupinus excubitus',
    'Quercus crysolepis',
    'Pseudotsuga macrocarpa',
    'Hypochaeris glabra',
    'Hordeum murinum',
    'Corethrogyne filaginifolia',
    'Lupinus arboreus',
    'Salvia mellifera',
    'Ceanothus integerrimus',
    'Spergularia villosa',
    'Platanus racemosa',
    'Chlorogalum pomeridianum',
    'Plagiobothrys nothofulvus',
    'Vicia villosa',
    'Astragalus brautonii',
    'Lupinus bicolor',
    'Heteromeles arbutifolia',
    'Grindelia camporum',
    'Quercus sp',
    'Quercus parvula',
    'Quercus berberidifolia',
    'Baccharis salicifolia',
    'Populus fremontii',
    'Juglans californica',
    'Stipa lepida',
    'Malacothamnus fasciculatus',
    'Anemopsis californica',
    'Pinus muricata',
    'Ericameria ericoides',
    'Eucalyptus globulus',
    'Dendromecon rigida',
    'Isocoma menziesii',
    'Rosa californica',
    'Pseudognaphalium californicum',
    'Juncus mexicanus',
    'Carex pansa',
    'Juncus patens',
    'Juniperus californica',
    'Cotula coronopifolia',
    'Distichlis spicata',
    'Juncus xiphioides',
    'Eleocharis macrostachya',
    'Elymus triticoides',
    'Elymus glaucus',
    'Pinus jeffreyi',
    'Baccharis glutinosa',
    'Muhlenbergia rigens',
    'Asclepias fascicularis',
    'Deinandra increscens',
    'Festuca perennis',
    'Jaumea carnosa',
    'Salicornia pacifica',
    'Frankenia salina',
    'Arthrocnemum subterminale',
    'not recorded'
); 