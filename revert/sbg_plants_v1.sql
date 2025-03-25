-- Revert sbgplants:sbg_plants_v1 from pg

BEGIN;

DROP TYPE IF EXISTS sbgplants."FRACTIONAL_class" CASCADE;
DROP TYPE IF EXISTS sbgplants."FRACTIONAL_method" CASCADE;
DROP TYPE IF EXISTS sbgplants."OBS_type" CASCADE;
DROP TYPE IF EXISTS sbgplants."PLOT_type" CASCADE;
DROP TYPE IF EXISTS sbgplants."Repository" CASCADE;
DROP TYPE IF EXISTS sbgplants."Sample_handling" CASCADE;
DROP TYPE IF EXISTS sbgplants."Trait" CASCADE;
DROP TYPE IF EXISTS sbgplants."Trait_method" CASCADE;
DROP TYPE IF EXISTS sbgplants."Trait_units" CASCADE;

-- Cannot drop this without droping postgis extension
-- DROP TABLE IF EXISTS sbgplants.spatial_ref_sys; 

DROP TABLE IF EXISTS sbgplants.plot CASCADE;
DROP TABLE IF EXISTS sbgplants.raster_plot_event CASCADE;
DROP TABLE IF EXISTS sbgplants.plot_event_metadata CASCADE;
DROP TABLE IF EXISTS sbgplants.sample_list CASCADE;
DROP TABLE IF EXISTS sbgplants.species_list CASCADE;
DROP TABLE IF EXISTS sbgplants.flightline CASCADE;
DROP TABLE IF EXISTS sbgplants.extracted_spectra;
DROP TABLE IF EXISTS sbgplants.insitu_plot_event;
DROP TABLE IF EXISTS sbgplants.sensor_campaign CASCADE;
DROP TABLE IF EXISTS sbgplants.pixel CASCADE;
DROP TABLE IF EXISTS sbgplants.extracted_observations;
DROP TABLE IF EXISTS sbgplants.scene CASCADE;
DROP TABLE IF EXISTS sbgplants.fractional_cover;
DROP TABLE IF EXISTS sbgplants.campaign;
DROP TABLE IF EXISTS sbgplants.leaf_properties;



COMMIT;
