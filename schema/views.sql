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
SELECT * from extracted_spectra;

GRANT SELECT ON plot_pixels_mv TO postgrest_user;
GRANT SELECT ON leaf_traits_view TO postgrest_user;
GRANT SELECT ON extracted_spectra_view TO postgrest_user;

DROP MATERIALIZED VIEW plot_pixels_mv;
DROP VIEW leaf_traits_view;
DROP  VIEW extracted_spectra_view;