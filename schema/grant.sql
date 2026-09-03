-- ---------------------------------------------------------------------------
-- postgrest_user
-- Read-only access to production and staging views served by the database API.
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA vswir_plants         TO postgrest_user;
GRANT USAGE ON SCHEMA vswir_plants_staging TO postgrest_user;

-- Production views
GRANT SELECT ON vswir_plants.plot_shape_view         TO postgrest_user;
GRANT SELECT ON vswir_plants.trait_view              TO postgrest_user;
GRANT SELECT ON vswir_plants.granule_view            TO postgrest_user;
GRANT SELECT ON vswir_plants.pixel                   TO postgrest_user;
GRANT SELECT ON vswir_plants.extracted_spectra_view  TO postgrest_user;
GRANT SELECT ON vswir_plants.extracted_metadata_view TO postgrest_user;
GRANT SELECT ON vswir_plants.reflectance_view        TO postgrest_user;

-- Staging views (schema-toggle feature — admin+ users only, enforced in the API)
GRANT SELECT ON vswir_plants_staging.plot_shape_view         TO postgrest_user;
GRANT SELECT ON vswir_plants_staging.trait_view              TO postgrest_user;
GRANT SELECT ON vswir_plants_staging.granule_view            TO postgrest_user;
GRANT SELECT ON vswir_plants_staging.extracted_spectra_view  TO postgrest_user;
GRANT SELECT ON vswir_plants_staging.extracted_metadata_view TO postgrest_user;
GRANT SELECT ON vswir_plants_staging.reflectance_view        TO postgrest_user;
GRANT SELECT ON vswir_plants_staging.pixel                   TO postgrest_user;

-- ---------------------------------------------------------------------------
-- isofit
-- Reads radiance spectra and sensor metadata; writes reflectance output.
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA vswir_plants TO isofit;

GRANT SELECT ON vswir_plants.extracted_spectra_view  TO isofit;
GRANT SELECT ON vswir_plants.extracted_metadata_view TO isofit;
GRANT SELECT ON vswir_plants.reflectance_view        TO isofit;

GRANT INSERT, UPDATE, SELECT
    ON vswir_plants.output_pixel_rfl TO isofit;

-- Staging: isofit writes reflectance results here before promotion
GRANT USAGE ON SCHEMA vswir_plants_staging TO isofit;
GRANT INSERT, UPDATE, SELECT, DELETE
    ON vswir_plants_staging.output_pixel_rfl TO isofit;

-- ---------------------------------------------------------------------------
-- ingestion_staging
-- Used by the QAQC and rejection lambdas.
--   - Full read/write on staging tables (load and delete batches)
--   - Read-only on production tables (cross-reference during QAQC checks)
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA vswir_plants_staging TO ingestion_staging;
GRANT USAGE ON SCHEMA vswir_plants         TO ingestion_staging;

-- Staging: full read/write on all tables
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA vswir_plants_staging TO ingestion_staging;

-- Staging: sequences needed for SERIAL columns
GRANT USAGE ON ALL SEQUENCES IN SCHEMA vswir_plants_staging TO ingestion_staging;

-- Production: read-only for QAQC cross-referencing
GRANT SELECT ON vswir_plants.campaign               TO ingestion_staging;
GRANT SELECT ON vswir_plants.sensor_campaign        TO ingestion_staging;
GRANT SELECT ON vswir_plants.granule                TO ingestion_staging;
GRANT SELECT ON vswir_plants.plot                   TO ingestion_staging;
GRANT SELECT ON vswir_plants.plot_shape             TO ingestion_staging;
GRANT SELECT ON vswir_plants.plot_raster_intersect  TO ingestion_staging;
GRANT SELECT ON vswir_plants.pixel                  TO ingestion_staging;
GRANT SELECT ON vswir_plants.extracted_spectra      TO ingestion_staging;
GRANT SELECT ON vswir_plants.insitu_plot_event      TO ingestion_staging;
GRANT SELECT ON vswir_plants.sample                 TO ingestion_staging;
GRANT SELECT ON vswir_plants.leaf_traits            TO ingestion_staging;
GRANT SELECT ON vswir_plants.doi                    TO ingestion_staging;

-- ---------------------------------------------------------------------------
-- ingestion_promotion
-- Used by the promotion lambda only.
--   - Read + delete on staging (read batches to promote, rows cascade-delete)
--   - Insert + select on all production ingestion-target tables
--   - Usage on production sequences (for serial ID generation)
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA vswir_plants_staging TO ingestion_promotion;
GRANT USAGE ON SCHEMA vswir_plants         TO ingestion_promotion;

-- Staging: read and delete
GRANT SELECT, DELETE
    ON ALL TABLES IN SCHEMA vswir_plants_staging TO ingestion_promotion;

-- Production: insert + select on all ingestion-target tables
GRANT SELECT, INSERT ON vswir_plants.campaign              TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.sensor_campaign       TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.granule               TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.plot_shape            TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.plot                  TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.plot_raster_intersect TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.insitu_plot_event     TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.sample                TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.leaf_traits           TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.pixel                 TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.extracted_spectra     TO ingestion_promotion;
GRANT SELECT, INSERT ON vswir_plants.doi                   TO ingestion_promotion;

-- Production: sequences for serial ID generation on promotion
GRANT USAGE ON ALL SEQUENCES IN SCHEMA vswir_plants TO ingestion_promotion;
