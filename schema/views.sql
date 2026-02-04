CREATE MATERIALIZED VIEW vswir_plants.plot_pixels_mv AS
SELECT
    ROW_NUMBER() OVER () AS id, 
    pri.plot_id,
    pl.plot_name,
    g.campaign_name,
    g.sensor_name,
    pri.granule_id,
    to_char(to_date(substring(pri.granule_id from '\d{8}'), 'YYYYMMDD'), 'YYYY-MM-DD') AS granule_date,
    -- aggregate pixel_ids for this plot+granule
    jsonb_agg(p.pixel_id ORDER BY p.pixel_id) AS pixel_ids,
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


-- GIST index for geometry (spatial queries)
CREATE INDEX idx_plot_pixels_geom ON vswir_plants.plot_pixels_mv USING GIST (geom);
-- B-tree index on plot_id (or plot_name) for filtering by plot
CREATE INDEX idx_plot_pixels_plot ON vswir_plants.plot_pixels_mv (plot_name);
-- B-tree index on granule_date for filtering by date
CREATE INDEX idx_plot_pixels_date ON vswir_plants.plot_pixels_mv (granule_date);
-- Optional: combined index if you often filter by plot + granule_date together
CREATE INDEX idx_plot_pixels_plot_date ON vswir_plants.plot_pixels_mv (plot_name, granule_date);


CREATE MATERIALIZED VIEW vswir_plants.insitu_sample_trait_mv AS
SELECT
ROW_NUMBER() OVER () AS id,
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

CREATE INDEX idx_leaf_traits_geom ON vswir_plants.insitu_sample_trait_mv USING GIST (geom);


CREATE MATERIALIZED VIEW pixel_spectra_mv AS
SELECT
    pp.plot_name,
    pp.granule_id,
    pp.granule_date,
    pid.pixel_id::integer AS pixel_id,
    es.radiance
FROM vswir_plants.plot_pixels_mv pp

JOIN LATERAL jsonb_array_elements_text(pp.pixel_ids) AS pid(pixel_id) ON TRUE
JOIN extracted_spectra es
    ON es.pixel_id = pid.pixel_id::integer;

CREATE INDEX pixel_spectra_mv_granule_id_idx
ON pixel_spectra_mv (granule_id);

CREATE INDEX pixel_spectra_mv_pixel_id_idx
ON pixel_spectra_mv (pixel_id);

CREATE INDEX pixel_spectra_mv_plot_name_idx
ON pixel_spectra_mv (plot_name);


GRANT SELECT ON plot_pixels_mv TO postgrest_user;
GRANT SELECT ON insitu_sample_trait_mv TO postgrest_user;
GRANT SELECT ON pixel_spectra_mv TO postgrest_user;

DROP MATERIALIZED VIEW plot_pixels_mv;
DROP MATERIALIZED VIEW insitu_sample_trait_mv;
DROP MATERIALIZED VIEW pixel_spectra_mv;
