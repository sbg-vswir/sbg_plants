CREATE MATERIALIZED VIEW vswir_plants.plot_pixels_mv AS
SELECT
    pri.plot_id,
    pl.plot_name,
    g.campaign_name,
    g.sensor_name,
    pri.granule_id,
    to_date(substring(pri.granule_id from '\d{8}'), 'YYYYMMDD') AS granule_date,
    jsonb_agg(p.pixel_id ORDER BY p.pixel_id) AS pixel_ids,   -- aggregate pixel_ids for this plot+granule
    ps.geom
FROM plot_raster_intersect pri
JOIN plot pl ON pl.plot_id = pri.plot_id
JOIN plot_shape ps ON ps.plot_shape_id = pri.plot_shape_id
JOIN granule g ON g.granule_id = pri.granule_id
JOIN pixel p ON p.granule_id = pri.granule_id
GROUP BY
    pri.plot_id,
    pl.plot_name,
    g.campaign_name,
    g.sensor_name,
    pri.granule_id,
    granule_date,
    geom;

CREATE INDEX idx_plot_pixels_geom ON vswir_plants.plot_pixels_mv USING GIST (geom);
CREATE INDEX idx_plot_pixels_date ON vswir_plants.plot_pixels_mv (granule_date);


CREATE VIEW vswir_plants.leaf_traits_view AS
SELECT
p.campaign_name,
p.site_id,
p.plot_name,
lt.sample_name,
lt.collection_date::text AS collection_date,
lt.trait,
lt.value,
lt.units,
lt.method,
lt.handling,
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
p.plot_method,
ps.geom
FROM leaf_traits lt
JOIN sample s ON s.plot_id = lt.plot_id AND s.collection_date = s.collection_date AND s.sample_name = lt.sample_name
JOIN insitu_plot_event ipe ON ipe.plot_id = s.plot_id AND ipe.collection_date = s.collection_date
JOIN plot p ON p.plot_id = ipe.plot_id
JOIN plot_raster_intersect pri ON pri.plot_id = p.plot_id
JOIN plot_shape ps ON ps.plot_shape_id = pri.plot_shape_id;

CREATE VIEW extracted_spectra_view AS
SELECT
es.pixel_id, 
es.radiance,
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
p.granule_id
-- g.campaign_name,
-- g.sensor_name
FROM pixel p
JOIN extracted_spectra es ON es.pixel_id = p.pixel_id;
-- JOIN granule g ON g.granule_id = p.granule_id

CREATE VIEW extracted_metadata_view AS
SELECT
sc.campaign_name,
sc.sensor_name,
sc.elevation_source,
sc.wavelength_center,
sc.fwhm
FROM sensor_campaign sc; 
-- JOIN granule g ON sc.campaign_name = g.campaign_name AND sc.sensor_name = g.sensor_name;



CREATE VIEW reflectance_view AS
SELECT
opr.pixel_id,
opr.reflectance
FROM output_pixel_rfl opr;
-- JOIN pixel p ON p.pixel_id = opr.pixel_id
-- Join granule g ON g.granule_id = p.granule_id
-- JOIN sensor_campaign sc ON sc.campaign_name = g.campaign_name AND sc.sensor_name = g.sensor_name;

GRANT SELECT ON plot_pixels_mv TO postgrest_user;
GRANT SELECT ON leaf_traits_view TO postgrest_user;
GRANT SELECT ON extracted_spectra_view TO postgrest_user;
GRANT SELECT ON extracted_metadata_view TO postgrest_user;
GRANT SELECT ON reflectance_view TO postgrest_user;

DROP MATERIALIZED VIEW plot_pixels_mv;
DROP VIEW leaf_traits_view;
DROP VIEW extracted_spectra_view;
DROP VIEW extracted_metadata_view;


-- GRANT SELECT ON extracted_spectra, output_pixel_rfl, sensor_campaign TO isofit;
GRANT SELECT ON extracted_spectra_view, extracted_metadata_view, reflectance_view TO isofit;
GRANT INSERT ON output_pixel_rfl TO isofit;
GRANT UPDATE ON output_pixel_rfl TO isofit;
GRANT USAGE ON SCHEMA vswir_plants TO isofit;