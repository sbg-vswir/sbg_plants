# Enum Values

Valid values for all enum columns across the ingestion files.

---

## `data_repository`

Used in: `campaign_metadata.csv`

- `ORNL DAAC`
- `NEON`
- `ECOSIS`
- `ESS-DIVE`

---

## `sensor_name`

Used in: `campaign_metadata.csv`, `granule_metadata.csv`, `spectra.csv`

- `NEON AIS 1`
- `NEON AIS 2`
- `NEON AIS 3`
- `AVIRIS-Classic`
- `AVIRIS-NG`
- `AVIRIS-3`
- `AVIRIS-5`

---

## `elevation_source`

Used in: `campaign_metadata.csv`

- `NEON AOP Lidar`
- `Copernicus 30m DEM`

---

## `cloudy_conditions`

Used in: `granule_metadata.csv`

- `Red`
- `Yellow`
- `Green`
- `Not recorded`

---

## `cloud_type`

Used in: `granule_metadata.csv`

- `Clear Sky`
- `Haze`
- `Cumulus`
- `Cumulus - sun obscured`
- `Cumulus - sun not obscured`
- `Cumulus / Cirrus`
- `Cumulus / Clear`
- `Cirrus`
- `Cirrus - sun obscured`
- `Cirrus - sun not obscured`
- `Cirrus / Clear`
- `Stratus`
- `Stratus - sun obscured`
- `Stratus - sun not obscured`
- `Complete stratus cover`
- `Unknown cloud type`
- `Not Collected`

---

## `plot_method`

Used in: `plots.geojson`

- `Individual`
- `Transect`
- `Plot`
- `Clip strip`

---

## `extraction_method`

Used in: `plots.geojson`

- `Internal centroids`
- `Full intersection`
- `Buffer`

---

## `delineation_method`

Used in: `plots.geojson`

- `Posthoc`
- `Radius Buffer`
- `In Field`

---

## `plot_veg_type`

Used in: `traits.csv`

- `Meadow`
- `Shrub`
- `Tree`
- `Grassland`
- `Not recorded`

---

## `subplot_cover_method`

Used in: `traits.csv`

- `Point`
- `Line-intercept-transect`
- `Quadrat`
- `Visual assessment`
- `N/A`

---

## `taxa`

Used in: `traits.csv`

- `Acomastylis rossii`
- `Agastache urticifolia`
- `Agrostis spp`
- `Alnus incana`
- `Anemone multifida`
- `Anemonastrum narcissiflorum`
- `Aquilegia coerulea`
- `Arnica mollis`
- `Arnica parryi`
- `Artemisia dracunculus`
- `Artemisia tridentata`
- `Abies lasiocarpa`
- `Betula glandulosa`
- `Bistorta bistortoides`
- `Bromopsis inermis`
- `Calamagrostis stricta`
- `Carex aquatilis`
- `Carex hoodii`
- `Carex lenticularis`
- `Carex microptera`
- `Carex siccata`
- `Carex spp`
- `Carex utriculata`
- `Castilleja rhexiifolia`
- `Castilleja sulphurea`
- `Chamerion danielsii`
- `Clementsia rhodantha`
- `Corydalis caseana`
- `Delphinium barbeyi`
- `Deschampsia cespitosa`
- `Distegia involucrata`
- `Dugaldia hoopesii`
- `Elymus lanceolatus`
- `Elymus spp`
- `Erigeron glacialis`
- `Erigeron speciosus`
- `Erythronium grandiflorum`
- `Eucephalus engelmannii`
- `Festuca idahoensis`
- `Festuca thurberi`
- `Festuca spp`
- `Fragaria virgiana`
- `Frasera speciosa`
- `Galium boreale`
- `Geranium richardsonii`
- `Helianthella quinquenervis`
- `Heliomeris multiflora`
- `Heracleum maximum`
- `Heterotheca villosa`
- `Hydrophyllum fendleri`
- `Iris missouriensis`
- `Juncus arcticus`
- `Juniperus communis`
- `Lathyrus lanszwertii`
- `Ligusticum porteri`
- `Linum lewisii`
- `Lupinus argenteus`
- `Lupinus bakeri`
- `Mertensia ciliata`
- `Mertensia lanceolata`
- `Osmorhiza occidentalis`
- `Pedicularis groenlandica`
- `Pentaphylloides floribunda`
- `Picea engelmannii`
- `Pinus contorta`
- `Poa compressa`
- `Poa leptocoma`
- `Poa secunda`
- `Populus tremuloides`
- `Potentilla pulcherrima`
- `Pseudocymopterus montanus`
- `Psychrophila leptosepala`
- `Pyrrocoma crocea`
- `Ribes montigenum`
- `Rubus idaeus`
- `Rumex densiflorus`
- `Salix boothii`
- `Salix brachycarpa`
- `Salix drummondiana`
- `Salix geyeriana`
- `Salix glauca`
- `Salix planifolia`
- `Salix spp`
- `Salix wolfii`
- `Sambucus microbotrys`
- `Senecio crassulus`
- `Senecio serra`
- `Senecio triangularis`
- `Sibbaldia procumbens`
- `Solidago spp`
- `Sorbus scopulina`
- `Symphoricarpos rotundifolius`
- `Symphyotrichum spp`
- `Thalictrum fendleri`
- `Tolmachevia integrifolia`
- `Vaccinium cespitosum`
- `Valeriana edulis`
- `Valeriana occidentalis`
- `Veratrum tenuipetalum`
- `Vicia americana`
- `Wyethia amplexicaulis`
- `Wyethia spp`
- `Not recorded`

---

## `veg_or_cover_type`

Used in: `traits.csv`

- `Grass`
- `Forb`
- `Fern`
- `Low shrub`
- `Broadleaf`
- `Needleleaf`
- `Lichen`
- `Epiphyte or Hemiepiphyte`
- `Bare`
- `NPV`
- `Moss`
- `PV`
- `Water`
- `Herbaceous clip strip - NEON`
- `Woody individual`

---

## `phenophase`

Used in: `traits.csv`

- `Leaves fully expanded`
- `Leaves not fully expanded`
- `Leaves beginning to senesce`
- `Most leaves senesced`
- `Not recorded`

---

## `sample_fc_class`

Used in: `traits.csv`

- `pv`
- `npv`
- `soil`
- `water`
- `char`
- `snow`
- `flowers`
- `seeds`

---

## `plant_status`

Used in: `traits.csv`

- `Insect damaged`
- `Disease damaged`
- `Other damage`
- `Physically damaged`
- `Not recorded`
- `Flowering`
- `Fruit setting`
- `Fruiting`

---

## `trait`

Used in: `traits.csv`

- `wet weight`
- `dry weight`
- `LWC`
- `CRF`
- `Chl`
- `LMA`
- `LAI`
- `Nitrogen`
- `Phosphorus`
- `Magnesium`
- `Potassium`
- `Calcium`
- `Sulfur`
- `Boron`
- `Iron`
- `Manganese`
- `Copper`
- `Zinc`
- `Aluminum`
- `Sodium`

---

## `method`

Used in: `traits.csv`

- `Chemical analysis`
- `Benchtop spectral PLSR`
- `Field measured (CCM)`
- `Weight based`

---

## `handling`

Used in: `traits.csv`

- `Fresh`
- `Flash frozen`
- `Oven dried`

---

## `units`

Used in: `traits.csv`

- `g`
- `percentage`
- `ratio`
- `mg m-2`
- `grams dry mass per g m2`
- `concentration in percent dry mass`
- `concentration in ppm`

---

## `error_type`

Used in: `traits.csv`

- `Instrument precision`
- `Standard deviation of measurement`
- `Standard error of measurement`
