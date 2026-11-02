-- ── vswir_plants_staging views ───────────────────────────────────────────────
--
-- Mirrors the production views in plants_v5_views.sql for staged data.
-- Identical column names so VIEW_CONFIG in the database_api needs no changes —
-- only the schema prefix in the SQL changes.
--
-- A staged row can point at a parent that is already in production (a batch
-- can add samples to an existing plot, spectra to an existing granule, …).
-- plot_id / plot_shape_id / pixel_id are shared with production (staging takes
-- them from the production sequences), so parents are looked up in
-- staging ∪ production. Production rows carry batch_id NULL in the unions, and
-- staging-to-staging joins also match on batch_id so two batches staging the
-- same key don't mix.
--
-- reflectance_view is special: output_pixel_rfl in staging holds production
-- pixel_ids (isofit receives pixels directly from the production
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
DROP VIEW IF EXISTS vswir_plants_staging.all_plot;
DROP VIEW IF EXISTS vswir_plants_staging.all_granule;

-- ── all_plot / all_granule (helpers) ──────────────────────────────────────────
-- Staged rows plus production rows, for joining staged children to parents
-- that may live in either schema. Not granted to postgrest_user.

CREATE VIEW vswir_plants_staging.all_plot AS
SELECT plot_id, campaign_name, site_id, plot_name, plot_method, batch_id
FROM vswir_plants_staging.plot
UNION ALL
SELECT plot_id, campaign_name::text, site_id, plot_name, plot_method, NULL
FROM vswir_plants.plot;

CREATE VIEW vswir_plants_staging.all_granule AS
SELECT granule_id, campaign_name, sensor_name, sensor_date, acquisition_date,
       acquisition_start_time, cloudy_conditions, cloud_type, gsd, flightline_id,
       granule_rad_url, granule_refl_url, raster_epsg, batch_id
FROM vswir_plants_staging.granule
UNION ALL
SELECT granule_id, campaign_name::text, sensor_name, sensor_date, acquisition_date,
       acquisition_start_time, cloudy_conditions, cloud_type, gsd, flightline_id,
       granule_rad_url, granule_refl_url, raster_epsg, NULL
FROM vswir_plants.granule;

-- ── trait_view ────────────────────────────────────────────────────────────────
-- Staged samples (with their staged traits), plus production samples that
-- have staged traits (new traits added to an existing sample).

CREATE VIEW vswir_plants_staging.trait_view AS
WITH samples AS (
    SELECT plot_id, collection_date, sample_name, taxa, veg_or_cover_type,
           phenophase, sample_fc_class, sample_fc_percent, canopy_position,
           plant_status, batch_id
    FROM vswir_plants_staging.sample
    UNION ALL
    SELECT s.plot_id, s.collection_date, s.sample_name, s.taxa, s.veg_or_cover_type,
           s.phenophase, s.sample_fc_class, s.sample_fc_percent, s.canopy_position,
           s.plant_status, NULL
    FROM vswir_plants.sample s
    WHERE EXISTS (
        SELECT 1 FROM vswir_plants_staging.leaf_traits lt
        WHERE lt.plot_id = s.plot_id
          AND lt.collection_date = s.collection_date
          AND lt.sample_name = s.sample_name
    )
),
events AS (
    SELECT plot_id, collection_date, plot_veg_type, subplot_cover_method,
           floristic_survey, batch_id
    FROM vswir_plants_staging.insitu_plot_event
    UNION ALL
    SELECT plot_id, collection_date, plot_veg_type, subplot_cover_method,
           floristic_survey, NULL
    FROM vswir_plants.insitu_plot_event
)
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
    -- trait (NULL if sample has no staged trait measurements)
    lt.trait,
    lt.value,
    lt.units,
    lt.method,
    lt.handling,
    lt.error,
    lt.error_type
FROM samples s
JOIN events ipe
    ON ipe.plot_id = s.plot_id
    AND ipe.collection_date = s.collection_date
    AND (ipe.batch_id IS NULL OR ipe.batch_id = s.batch_id)
JOIN vswir_plants_staging.all_plot p
    ON p.plot_id = ipe.plot_id
    AND (p.batch_id IS NULL OR p.batch_id = s.batch_id)
LEFT JOIN vswir_plants_staging.leaf_traits lt
    ON lt.plot_id = s.plot_id
    AND lt.collection_date = s.collection_date
    AND lt.sample_name = s.sample_name
    AND (s.batch_id IS NULL OR lt.batch_id = s.batch_id);

-- ── plot_shape_view ───────────────────────────────────────────────────────────
-- Intersects and shapes are always new in a batch; the plot may be in production.

CREATE VIEW vswir_plants_staging.plot_shape_view AS
SELECT DISTINCT ON (p.plot_id, ps.plot_shape_id)
    p.plot_id,
    p.plot_name,
    p.campaign_name,
    p.site_id,
    p.plot_method,
    ps.plot_shape_id,
    ps.geom
FROM vswir_plants_staging.plot_raster_intersect pri
JOIN vswir_plants_staging.all_plot p
    ON p.plot_id = pri.plot_id
    AND (p.batch_id IS NULL OR p.batch_id = pri.batch_id)
JOIN vswir_plants_staging.plot_shape ps
    ON ps.plot_shape_id = pri.plot_shape_id
    AND ps.batch_id = pri.batch_id;

-- ── granule_view ──────────────────────────────────────────────────────────────
-- Staged granules, plus production granules that staged pixels point at
-- (a spectra-only batch for an existing granule).

CREATE VIEW vswir_plants_staging.granule_view AS
SELECT
    g.granule_id,
    g.campaign_name,
    g.sensor_name,
    g.sensor_date,
    g.acquisition_date,
    g.acquisition_start_time,
    g.cloudy_conditions,
    g.cloud_type,
    g.gsd,
    g.flightline_id,
    g.granule_rad_url,
    g.granule_refl_url,
    g.raster_epsg
FROM vswir_plants_staging.all_granule g
WHERE g.batch_id IS NOT NULL
   OR EXISTS (SELECT 1 FROM vswir_plants_staging.pixel px WHERE px.granule_id = g.granule_id);

-- ── extracted_spectra_view ────────────────────────────────────────────────────

CREATE VIEW vswir_plants_staging.extracted_spectra_view AS
SELECT
    es.pixel_id,
    g.campaign_name,
    g.sensor_name,
    g.sensor_date,
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
JOIN vswir_plants_staging.all_granule g
    ON g.granule_id = p.granule_id
    AND (g.batch_id IS NULL OR g.batch_id = p.batch_id)
JOIN vswir_plants_staging.all_plot pl
    ON pl.plot_id = p.plot_id
    AND (pl.batch_id IS NULL OR pl.batch_id = p.batch_id);

-- ── extracted_metadata_view ───────────────────────────────────────────────────
-- Staged sensor calibrations plus production ones, so staged spectra over a
-- calibration that is already in production still find their wavelengths.
-- UNION (not UNION ALL) collapses two batches staging the identical row.

CREATE VIEW vswir_plants_staging.extracted_metadata_view AS
SELECT
    sc.campaign_name,
    sc.sensor_name,
    sc.sensor_date,
    sc.elevation_source,
    sc.wavelength_center,
    sc.fwhm
FROM vswir_plants_staging.sensor_campaign sc
UNION
SELECT
    sc.campaign_name::text,
    sc.sensor_name,
    sc.sensor_date,
    sc.elevation_source,
    sc.wavelength_center,
    sc.fwhm
FROM vswir_plants.sensor_campaign sc;

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
    g.sensor_date,
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
