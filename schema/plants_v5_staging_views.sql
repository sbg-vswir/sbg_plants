-- ── vswir_plants_staging views ───────────────────────────────────────────────
--
-- Mirrors the production views in views_v2.sql, joining staging tables instead
-- of production tables. Identical column names and types so VIEW_CONFIG in the
-- database_api needs no changes — only the schema prefix in the SQL changes.
--
-- Staging tables carry a batch_id column not present in production. The views
-- do not expose batch_id; join conditions include it where needed because
-- staging primary keys are composite (id + batch_id).
--
-- reflectance_view is special: output_pixel_rfl in staging holds production-
-- space pixel_ids (isofit receives pixels directly from the production
-- extracted_spectra_view), so its JOINs go to vswir_plants, not staging.
--
-- Grants for postgrest_user on these views are in grant.sql.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Drop Commands ─────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS vswir_plants_staging.trait_view;
DROP VIEW IF EXISTS vswir_plants_staging.plot_shape_view;
DROP VIEW IF EXISTS vswir_plants_staging.granule_view;
DROP VIEW IF EXISTS vswir_plants_staging.extracted_spectra_view;
DROP VIEW IF EXISTS vswir_plants_staging.extracted_metadata_view;
DROP VIEW IF EXISTS vswir_plants_staging.reflectance_view;

-- ── trait_view ────────────────────────────────────────────────────────────────

CREATE VIEW vswir_plants_staging.trait_view AS
SELECT
    -- plot identity
    p.plot_id,
    p.plot_name,
    p.campaign_name,
    p.site_id,
    p.plot_method,
    -- plot event
    ipe.collection_date,
    ipe.plot_veg_type,
    ipe.subplot_cover_method,
    ipe.floristic_survey,
    -- sample
    s.sample_name,
    s.taxa,
    s.veg_or_cover_type,
    s.phenophase,
    s.sample_fc_class,
    s.sample_fc_percent,
    s.canopy_position,
    s.plant_status,
    -- trait (NULL if sample has no trait measurements)
    lt.trait,
    lt.value,
    lt.units,
    lt.method,
    lt.handling,
    lt.error,
    lt.error_type
FROM vswir_plants_staging.sample s
JOIN vswir_plants_staging.insitu_plot_event ipe
    ON ipe.plot_id = s.plot_id
    AND ipe.collection_date = s.collection_date
    AND ipe.batch_id = s.batch_id
JOIN vswir_plants_staging.plot p
    ON p.plot_id = ipe.plot_id
    AND p.batch_id = ipe.batch_id
LEFT JOIN vswir_plants_staging.leaf_traits lt
    ON lt.plot_id = s.plot_id
    AND lt.collection_date = s.collection_date
    AND lt.sample_name = s.sample_name
    AND lt.batch_id = s.batch_id;

-- ── plot_shape_view ───────────────────────────────────────────────────────────

CREATE VIEW vswir_plants_staging.plot_shape_view AS
SELECT DISTINCT ON (p.plot_id, ps.plot_shape_id)
    p.plot_id,
    p.plot_name,
    p.campaign_name,
    p.site_id,
    p.plot_method,
    ps.plot_shape_id,
    ps.geom
FROM vswir_plants_staging.plot p
JOIN vswir_plants_staging.plot_raster_intersect pri
    ON pri.plot_id = p.plot_id
    AND pri.batch_id = p.batch_id
JOIN vswir_plants_staging.plot_shape ps
    ON ps.plot_shape_id = pri.plot_shape_id
    AND ps.batch_id = pri.batch_id;

-- ── granule_view ──────────────────────────────────────────────────────────────

CREATE VIEW vswir_plants_staging.granule_view AS
SELECT
    g.granule_id,
    g.campaign_name,
    g.sensor_name,
    g.acquisition_date,
    g.acquisition_start_time,
    g.cloudy_conditions,
    g.cloud_type,
    g.gsd,
    g.flightline_id,
    g.granule_rad_url,
    g.granule_refl_url,
    g.raster_epsg
FROM vswir_plants_staging.granule g;

-- ── extracted_spectra_view ────────────────────────────────────────────────────

CREATE VIEW vswir_plants_staging.extracted_spectra_view AS
SELECT
    es.pixel_id,
    g.campaign_name,
    g.sensor_name,
    p.granule_id,
    g.acquisition_date,
    g.acquisition_start_time,
    p.plot_id,
    pl.plot_name,
    p.lon,
    p.lat,
    p.elevation,
    p.path_length,
    p.to_sensor_azimuth,
    p.to_sensor_zenith,
    p.to_sun_azimuth,
    p.to_sun_zenith,
    p.solar_phase,
    p.slope,
    p.aspect,
    p.cosine_i,
    p.utc_time,
    p.shade_mask,
    es.radiance
FROM vswir_plants_staging.pixel p
JOIN vswir_plants_staging.extracted_spectra es
    ON es.pixel_id = p.pixel_id
    AND es.batch_id = p.batch_id
JOIN vswir_plants_staging.granule g
    ON g.granule_id = p.granule_id
    AND g.batch_id = p.batch_id
JOIN vswir_plants_staging.plot pl
    ON pl.plot_id = p.plot_id
    AND pl.batch_id = p.batch_id;

-- ── extracted_metadata_view ───────────────────────────────────────────────────

CREATE VIEW vswir_plants_staging.extracted_metadata_view AS
SELECT
    sc.campaign_name,
    sc.sensor_name,
    sc.elevation_source,
    sc.wavelength_center,
    sc.fwhm
FROM vswir_plants_staging.sensor_campaign sc;

-- ── reflectance_view ──────────────────────────────────────────────────────────
-- output_pixel_rfl in staging holds pixel_ids from production-space (isofit
-- receives pixels directly from the production extracted_spectra_view).
-- The JOIN therefore goes to vswir_plants (production) for pixel/granule/plot.
--
-- DISTINCT ON (pixel_id) with ORDER BY job_id DESC means that when the same
-- pixel has been processed by multiple jobs, only the most recent job's result
-- is returned (job_ids are UUIDs with a timestamp prefix so lexicographic DESC
-- is chronologically latest).

CREATE VIEW vswir_plants_staging.reflectance_view AS
SELECT DISTINCT ON (opr.pixel_id)
    opr.pixel_id,
    opr.job_id,
    g.campaign_name,
    g.sensor_name,
    p.granule_id,
    g.acquisition_date,
    g.acquisition_start_time,
    p.plot_id,
    pl.plot_name,
    p.lon,
    p.lat,
    p.elevation,
    g.cloudy_conditions,
    g.cloud_type,
    opr.reflectance
FROM vswir_plants_staging.output_pixel_rfl opr
JOIN vswir_plants.pixel p ON p.pixel_id = opr.pixel_id
JOIN vswir_plants.granule g ON g.granule_id = p.granule_id
JOIN vswir_plants.plot pl ON pl.plot_id = p.plot_id
ORDER BY opr.pixel_id, opr.job_id DESC;