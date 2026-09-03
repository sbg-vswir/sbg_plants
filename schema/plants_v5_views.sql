-- ── Drop Commands ─────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS vswir_plants.trait_view;
DROP VIEW IF EXISTS vswir_plants.plot_shape_view;
DROP VIEW IF EXISTS vswir_plants.granule_view;
DROP VIEW IF EXISTS vswir_plants.extracted_spectra_view;
DROP VIEW IF EXISTS vswir_plants.extracted_metadata_view;
DROP VIEW IF EXISTS vswir_plants.reflectance_view;

-- ── trait_view ────────────────────────────────────────────────────────────────
-- One row per (sample, trait). Samples without trait measurements appear once
-- with NULL trait columns. Anchored on sample so all samples are included
-- regardless of whether they have associated trait measurements.

CREATE VIEW vswir_plants.trait_view AS
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
FROM vswir_plants.sample s
JOIN vswir_plants.insitu_plot_event ipe
    ON ipe.plot_id = s.plot_id
    AND ipe.collection_date = s.collection_date
JOIN vswir_plants.plot p
    ON p.plot_id = ipe.plot_id
LEFT JOIN vswir_plants.leaf_traits lt
    ON lt.plot_id = s.plot_id
    AND lt.collection_date = s.collection_date
    AND lt.sample_name = s.sample_name;

-- ── plot_shape_view ───────────────────────────────────────────────────────────
-- One row per (plot, shape). Multiple shapes per plot are preserved — a plot
-- can have multiple shapes from different field seasons or delineations.
-- DISTINCT ON (plot_id, plot_shape_id) deduplicates on integer primary keys
-- only — geometry is selected but not compared, keeping this efficient.
-- Row count equals the length of the plot_shape table.

CREATE VIEW vswir_plants.plot_shape_view AS
SELECT DISTINCT ON (p.plot_id, ps.plot_shape_id)
    p.plot_id,
    p.plot_name,
    p.campaign_name,
    p.site_id,
    p.plot_method,
    ps.plot_shape_id,
    ps.geom
FROM vswir_plants.plot p
JOIN vswir_plants.plot_raster_intersect pri ON pri.plot_id = p.plot_id
JOIN vswir_plants.plot_shape ps ON ps.plot_shape_id = pri.plot_shape_id;

-- ── granule_view ──────────────────────────────────────────────────────────────
-- One row per granule. Raw granule table columns only — no pixel aggregation.
-- Pixel IDs are aggregated at query time after filtering has been applied.
-- Campaign/sensor metadata (wavelength_center, fwhm) is available separately
-- via extracted_metadata_view and joined when needed.

CREATE VIEW vswir_plants.granule_view AS
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
FROM vswir_plants.granule g;

-- ── extracted_spectra_view ────────────────────────────────────────────────────
-- One row per pixel with full radiance array. Used by POST /query/spectra
-- (async — dispatched via SQS, results written to S3).

CREATE VIEW vswir_plants.extracted_spectra_view AS
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
FROM vswir_plants.pixel p
JOIN vswir_plants.extracted_spectra es ON es.pixel_id = p.pixel_id
JOIN vswir_plants.granule g ON g.granule_id = p.granule_id
JOIN vswir_plants.plot pl ON pl.plot_id = p.plot_id;

-- ── extracted_metadata_view ───────────────────────────────────────────────────
-- One row per (campaign, sensor). Provides wavelength centers and FWHM used
-- by the frontend to build spectra CSV headers. Used by GET /query/metadata.

CREATE VIEW vswir_plants.extracted_metadata_view AS
SELECT
    sc.campaign_name,
    sc.sensor_name,
    sc.elevation_source,
    sc.wavelength_center,
    sc.fwhm
FROM vswir_plants.sensor_campaign sc;

-- ── reflectance_view ──────────────────────────────────────────────────────────
-- One row per pixel with full reflectance array. Used by POST /query/reflectance
-- (async — dispatched via SQS, results written to S3).

CREATE VIEW vswir_plants.reflectance_view AS
SELECT
    opr.pixel_id,
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
FROM vswir_plants.output_pixel_rfl opr
JOIN vswir_plants.pixel p ON p.pixel_id = opr.pixel_id
JOIN vswir_plants.granule g ON g.granule_id = p.granule_id
JOIN vswir_plants.plot pl ON pl.plot_id = p.plot_id;
