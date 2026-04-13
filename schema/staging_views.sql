CREATE VIEW vswir_plants_staging.staging_plot_pixels_v AS
SELECT
    pri.plot_id,
    pl.plot_name,
    g.campaign_name,
    g.sensor_name,
    pri.granule_id,
    g.acquisition_date,
    g.cloudy_conditions,
    g.cloud_type,
    g.gsd,
    pri.extraction_method,
    pri.delineation_method,
    pri.shape_aligned_to_granule,
    ps.geom,
    pri.batch_id
FROM vswir_plants_staging.plot_raster_intersect pri
JOIN vswir_plants_staging.plot pl
    ON pl.plot_id = pri.plot_id AND pl.batch_id = pri.batch_id
JOIN vswir_plants_staging.plot_shape ps
    ON ps.plot_shape_id = pri.plot_shape_id AND ps.batch_id = pri.batch_id
JOIN vswir_plants_staging.granule g
    ON g.granule_id = pri.granule_id AND g.batch_id = pri.batch_id;

-- ── staging_spectra_v ─────────────────────────────────────────────────────────
-- Joined pixel + spectra view for promotion lambda to read staging spectra
-- in the same shape as production extracted_spectra_view.

CREATE VIEW vswir_plants_staging.staging_spectra_v AS
SELECT
    es.pixel_id,
    p.plot_id,
    pl.plot_name,
    g.campaign_name,
    g.sensor_name,
    p.granule_id,
    p.glt_row,
    p.glt_column,
    p.lon,
    p.lat,
    p.elevation,
    p.shade_mask,
    p.path_length,
    p.to_sensor_azimuth,
    p.to_sensor_zenith,
    p.to_sun_azimuth,
    p.to_sun_zenith,
    p.solar_phase,
    p.slope,
    p.aspect,
    p.utc_time,
    p.cosine_i,
    p.raw_cosine_i,
    es.radiance,
    es.batch_id
FROM vswir_plants_staging.extracted_spectra es
JOIN vswir_plants_staging.pixel p
    ON p.pixel_id = es.pixel_id AND p.batch_id = es.batch_id
JOIN vswir_plants_staging.plot pl
    ON pl.plot_id = p.plot_id AND pl.batch_id = p.batch_id
JOIN vswir_plants_staging.granule g
    ON g.granule_id = p.granule_id AND g.batch_id = p.batch_id;

-- ── staging_traits_v ──────────────────────────────────────────────────────────
-- Joined traits view for promotion lambda.

CREATE VIEW vswir_plants_staging.staging_traits_v AS
SELECT
    lt.plot_id,
    pl.plot_name,
    pl.campaign_name,
    lt.collection_date,
    lt.sample_name,
    lt.trait,
    lt.value,
    lt.method,
    lt.handling,
    lt.units,
    lt.error,
    lt.error_type,
    s.taxa,
    s.veg_or_cover_type,
    s.phenophase,
    s.sample_fc_class,
    s.sample_fc_percent,
    s.canopy_position,
    s.plant_status,
    ipe.plot_veg_type,
    ipe.subplot_cover_method,
    ipe.floristic_survey,
    lt.batch_id
FROM vswir_plants_staging.leaf_traits lt
JOIN vswir_plants_staging.sample s
    ON s.plot_id = lt.plot_id
    AND s.collection_date = lt.collection_date
    AND s.sample_name = lt.sample_name
    AND s.batch_id = lt.batch_id
JOIN vswir_plants_staging.insitu_plot_event ipe
    ON ipe.plot_id = s.plot_id
    AND ipe.collection_date = s.collection_date
    AND ipe.batch_id = s.batch_id
JOIN vswir_plants_staging.plot pl
    ON pl.plot_id = lt.plot_id
    AND pl.batch_id = lt.batch_id;

-- ── permissions ───────────────────────────────────────────────────────────────

GRANT SELECT ON ALL TABLES IN SCHEMA vswir_plants_staging TO ingestion_staging;
GRANT SELECT ON ALL TABLES IN SCHEMA vswir_plants_staging TO ingestion_promotion;
