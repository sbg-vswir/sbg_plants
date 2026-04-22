-- ---------------------------------------------------------------------------
-- postgrest_user
-- Read-only access to the production views served by the database API.
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA vswir_plants TO postgrest_user;

-- v2 views (replaces plot_pixels_mv and leaf_traits_view)
GRANT SELECT ON vswir_plants.plot_shape_view         TO postgrest_user;
GRANT SELECT ON vswir_plants.trait_view              TO postgrest_user;
GRANT SELECT ON vswir_plants.granule_view            TO postgrest_user;
GRANT SELECT ON vswir_plants.pixel                   TO postgrest_user;
GRANT SELECT ON vswir_plants.extracted_spectra_view  TO postgrest_user;
GRANT SELECT ON vswir_plants.extracted_metadata_view TO postgrest_user;
GRANT SELECT ON vswir_plants.reflectance_view        TO postgrest_user;

-- ---------------------------------------------------------------------------
-- isofit
-- Reads radiance spectra and sensor metadata; writes reflectance output.
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA vswir_plants TO isofit;

GRANT SELECT ON vswir_plants.extracted_spectra_view  TO isofit;
GRANT SELECT ON vswir_plants.extracted_metadata_view TO isofit;
GRANT SELECT ON vswir_plants.reflectance_view         TO isofit;

GRANT INSERT, UPDATE, SELECT
    ON vswir_plants.output_pixel_rfl TO isofit;

-- ---------------------------------------------------------------------------
-- ingestion_staging
-- Used by the QAQC lambda and the rejection lambda.
--   - Full read/write on staging (load and delete batches)
--   - Read-only on production (cross-reference during QAQC checks)
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA vswir_plants_staging TO ingestion_staging;
GRANT USAGE ON SCHEMA vswir_plants         TO ingestion_staging;

-- Staging: full read/write on all tables and views
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

-- ---------------------------------------------------------------------------
-- ingestion_promotion
-- Used by the promotion lambda only.
--   - Read-only on staging (read batches to promote)
--   - Full insert + select on production tables
--   - Usage on production sequences (for re-generating serial IDs)
-- ---------------------------------------------------------------------------

GRANT USAGE ON SCHEMA vswir_plants_staging TO ingestion_promotion;
GRANT USAGE ON SCHEMA vswir_plants         TO ingestion_promotion;

-- Staging: read-only (promotion reads staging, then deletes via ON DELETE CASCADE
-- or direct DELETE — grant DELETE here if staging rows are deleted directly)
GRANT SELECT, DELETE
    ON ALL TABLES IN SCHEMA vswir_plants_staging TO ingestion_promotion;

-- Production: insert + select on all ingestion-target tables
GRANT SELECT, INSERT
    ON vswir_plants.campaign              TO ingestion_promotion;
GRANT SELECT, INSERT
    ON vswir_plants.sensor_campaign       TO ingestion_promotion;
GRANT SELECT, INSERT
    ON vswir_plants.granule               TO ingestion_promotion;
GRANT SELECT, INSERT
    ON vswir_plants.plot_shape            TO ingestion_promotion;
GRANT SELECT, INSERT
    ON vswir_plants.plot                  TO ingestion_promotion;
GRANT SELECT, INSERT
    ON vswir_plants.plot_raster_intersect TO ingestion_promotion;
GRANT SELECT, INSERT
    ON vswir_plants.insitu_plot_event     TO ingestion_promotion;
GRANT SELECT, INSERT
    ON vswir_plants.sample                TO ingestion_promotion;
GRANT SELECT, INSERT
    ON vswir_plants.leaf_traits           TO ingestion_promotion;
GRANT SELECT, INSERT
    ON vswir_plants.pixel                 TO ingestion_promotion;
GRANT SELECT, INSERT
    ON vswir_plants.extracted_spectra     TO ingestion_promotion;

-- Production: sequences for re-generating serial IDs on promotion
GRANT USAGE ON ALL SEQUENCES IN SCHEMA vswir_plants TO ingestion_promotion;

-- Production: refresh the materialized view after promotion
-- plot_pixels_mv has been retired; remove this grant when confirmed removed from DB.
-- GRANT SELECT ON vswir_plants.plot_pixels_mv TO ingestion_promotion;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY requires the user to own the view,
-- or be a superuser. In practice the promotion lambda runs as a superuser
-- role or the view owner executes the refresh via a SECURITY DEFINER function.
-- Uncomment and adapt if using a wrapper function:
-- GRANT EXECUTE ON FUNCTION vswir_plants.refresh_plot_pixels_mv() TO ingestion_promotion;
