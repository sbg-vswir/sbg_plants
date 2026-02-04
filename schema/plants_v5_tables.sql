-- doi table, neon dois change on a yearly basis
    -- drop down for what the data are
    -- one campaign many dois
CREATE TABLE vswir_plants.campaign (
    campaign_name VARCHAR PRIMARY KEY,
    primary_funding_source VARCHAR NOT NULL,
    data_repository vswir_plants."Repository",
    doi VARCHAR,
    taxa_system VARCHAR
);

-- elevation source does it need a version?
CREATE TABLE vswir_plants.sensor_campaign (
    campaign_name VARCHAR NOT NULL,
    sensor_name vswir_plants."Sensor_name" NOT NULL,
    elevation_source vswir_plants."ELEVATION_source" NOT NULL,
    wavelength_center FLOAT4[] NOT NULL,
    fwhm FLOAT4[] NOT NULL,
    CONSTRAINT sensor_campaign_fkey FOREIGN KEY (campaign_name)
        REFERENCES vswir_plants.campaign(campaign_name)
        ON DELETE CASCADE,
    CONSTRAINT sensor_campaign_pk PRIMARY KEY (campaign_name, sensor_name)
);

CREATE TABLE vswir_plants.plot (
    plot_id SERIAL PRIMARY KEY,
    campaign_name VARCHAR NOT NULL,
    site_id VARCHAR NOT NULL,
    plot_name VARCHAR NOT NULL,
    plot_method vswir_plants."PLOT_method",
    CONSTRAINT plot_campaign_name_fkey FOREIGN KEY (campaign_name)
        REFERENCES vswir_plants.campaign(campaign_name) 
        ON DELETE CASCADE
);

CREATE TABLE vswir_plants.granule (
    granule_id VARCHAR PRIMARY KEY,
    campaign_name VARCHAR NOT NULL,
    sensor_name vswir_plants."Sensor_name" NOT NULL,
    acquisition_start_time time NOT NULL,
    acquisition_date DATE NOT NULL,
    granule_rad_url VARCHAR,
    granule_refl_url VARCHAR,
    flightline_id VARCHAR,
    cloudy_conditions vswir_plants."CLOUD_conditions" NOT NULL,
    cloud_type vswir_plants. "CLOUD_type" NOT NULL,
    gsd FLOAT4 NOT NULL,
    raster_epsg INTEGER NOT NULL,
    CONSTRAINT granule_fkey FOREIGN KEY (campaign_name, sensor_name)
        REFERENCES vswir_plants.sensor_campaign(campaign_name, sensor_name)
        ON DELETE CASCADE
);

CREATE TABLE vswir_plants.plot_shape ( 
    plot_shape_id SERIAL PRIMARY KEY,
    geom geometry(POLYGON, 4326) NOT NULL 
);
    
CREATE INDEX plot_shape_idx ON vswir_plants.plot_shape USING GIST (geom);

CREATE TABLE vswir_plants.plot_raster_intersect ( 
    plot_id INTEGER NOT NULL,
    granule_id VARCHAR NOT NULL,
    plot_shape_id INTEGER NOT NULL,
    extraction_method vswir_plants."EXTRACTION_method" NOT NULL,
    delineation_method vswir_plants."DELINEATION_method" NOT NULL,
    shape_aligned_to_granule BOOLEAN NOT NULL,
    CONSTRAINT raster_plot_event_granule_id_fkey FOREIGN KEY (granule_id)
        REFERENCES vswir_plants.granule(granule_id)
        ON DELETE CASCADE,
    CONSTRAINT raster_plot_event_plot_name_fkey FOREIGN KEY (plot_id)
        REFERENCES vswir_plants.plot(plot_id)
        ON DELETE CASCADE,
    CONSTRAINT raster_plot_event_plot_shape_fkey FOREIGN KEY (plot_shape_id)
        REFERENCES vswir_plants.plot_shape(plot_shape_id)
        ON DELETE CASCADE,
    CONSTRAINT plot_raster_intersect_pk PRIMARY KEY (plot_id, granule_id)
);


CREATE TABLE vswir_plants.pixel (
    pixel_id SERIAL PRIMARY KEY,
    plot_id INTEGER NOT NULL,
    granule_id VARCHAR NOT NULL,
    glt_row INTEGER NOT NULL,
    glt_column INTEGER NOT NULL,
    shade_mask BOOLEAN NOT NULL,
    path_length FLOAT4 NOT NULL,
    to_sensor_azimuth FLOAT4 NOT NULL,
    to_sensor_zenith FLOAT4 NOT NULL,
    to_sun_azimuth FLOAT4 NOT NULL,
    to_sun_zenith FLOAT4 NOT NULL,
    solar_phase FLOAT4 NOT NULL,
    slope FLOAT4 NOT NULL,
    aspect FLOAT4 NOT NULL,
    utc_time FLOAT4 NOT NULL,
    cosine_i FLOAT4, -- needs to be not null in the future
    raw_cosine_i FLOAT4, -- needs to be not null in the future
    lon FLOAT4 NOT NULL, 
    lat FLOAT4 NOT NULL,
    elevation FLOAT4 NOT NULL,
    CONSTRAINT pixel_fkey FOREIGN KEY (plot_id, granule_id)
        REFERENCES vswir_plants.plot_raster_intersect(plot_id, granule_id)
        ON DELETE CASCADE
);
CREATE UNIQUE INDEX pixel_idx ON vswir_plants.pixel (plot_id, granule_id, glt_row, glt_column);


CREATE TABLE vswir_plants.extracted_spectra (
    pixel_id INTEGER NOT NULL,
    radiance FLOAT4[], 
    CONSTRAINT extracted_spectra_fkey FOREIGN KEY (pixel_id)
        REFERENCES vswir_plants.pixel(pixel_id)
        ON DELETE CASCADE,
    CONSTRAINT extracted_spectra_pk PRIMARY KEY (pixel_id)
);

CREATE TABLE vswir_plants.output_pixel_fc (
    pixel_id INTEGER PRIMARY KEY, 
    fc_class vswir_plants."FRACTIONAL_class",
    fc_percentage FLOAT4 NOT NULL,
    canopy_water_content FLOAT4 NOT NULL,
    uncertainty_cwc FLOAT4 NOT NULL,
    CONSTRAINT output_pixel_fc_pixel_fkey FOREIGN KEY (pixel_id)
        REFERENCES vswir_plants.pixel(pixel_id) 
        ON DELETE CASCADE
);

CREATE TABLE vswir_plants.output_pixel_rfl (
    pixel_id INTEGER PRIMARY KEY,
    reflectance FLOAT4[] NOT NULL,
    uncertainty_ref FLOAT4[] NOT NULL,
    CONSTRAINT output_pixel_rfl_pixel_fkey FOREIGN KEY (pixel_id)
        REFERENCES vswir_plants.pixel(pixel_id) 
        ON DELETE CASCADE
);

CREATE TABLE vswir_plants.insitu_plot_event (
    plot_id INTEGER NOT NULL,
    collection_date DATE NOT NULL,
    -- plot_shape_id INTEGER NOT NULL,
    plot_veg_type vswir_plants."VEGETATION_type" NOT NULL,
    subplot_cover_method vswir_plants."SUBPLOT_cover_method" NOT NULL,
    floristic_survey BOOLEAN NOT NULL,
    CONSTRAINT insitu_plot_event_plot_fkey FOREIGN KEY (plot_id)
        REFERENCES vswir_plants.plot(plot_id) 
        ON DELETE CASCADE,
    -- CONSTRAINT insitu_plot_event_plot_shape_fkey FOREIGN KEY (plot_shape_id)
    --     REFERENCES vswir_plants.plot_shape(plot_shape_id) 
    --     ON DELETE CASCADE,
    CONSTRAINT insitu_plot_event_pk PRIMARY KEY (plot_id, collection_date)
);


-- add canopy_position vswir.
CREATE TABLE vswir_plants.sample (
    collection_date DATE NOT NULL, 
    plot_id INTEGER NOT NULL,
    sample_name VARCHAR NOT NULL,
    taxa vswir_plants."TAXA" NOT NULL,
    veg_or_cover_type vswir_plants."VEG_or_cover_type" NOT NULL,
    phenophase vswir_plants."PHENOPHASE" NOT NULL,
    sample_fc_class vswir_plants."FRACTIONAL_class" NOT NULL,
    sample_fc_percent INTEGER NOT NULL,
    plant_status vswir_plants."PLANT_status" NOT NULL,
    CONSTRAINT sample_collection_date_plot_id_fkey FOREIGN KEY (plot_id, collection_date)
        REFERENCES vswir_plants.insitu_plot_event (plot_id, collection_date)
        ON DELETE CASCADE,
    CONSTRAINT sample_pk PRIMARY KEY (plot_id, collection_date, sample_name)
);

-- trait method to primary key, the same trait for the same sample could have several methods????
CREATE TABLE vswir_plants.leaf_traits (
    sample_name VARCHAR NOT NULL,
    plot_id INTEGER NOT NULL, 
    collection_date DATE NOT NULL,
    trait vswir_plants."Trait" NOT NULL,
    value FLOAT4 NOT NULL,
    method vswir_plants."Trait_method" NOT NULL,
    handling vswir_plants."Sample_handling" NOT NULL,
    units vswir_plants."Trait_units" NOT NULL,
    error FLOAT4,
    error_type vswir_plants."Error_type",
    CONSTRAINT sample_table_fkey FOREIGN KEY (plot_id, collection_date, sample_name)
        REFERENCES vswir_plants.sample (plot_id, collection_date, sample_name)
        ON DELETE CASCADE,
    CONSTRAINT leaf_trait_pk PRIMARY KEY (plot_id, collection_date, sample_name, trait)
);


-- CREATE TABLE vswir_plants.extracted_observations (
--     pixel_id INTEGER NOT NULL,
--     obs_type vswir_plants."OBS_type",
--     obs_value DOUBLE PRECISION,
--     CONSTRAINT extracted_observations_pixel_id_fkey FOREIGN KEY (pixel_id)
--         REFERENCES vswir_plants.pixel(pixel_id)
--         ON DELETE CASCADE,
--     CONSTRAINT extracted_obs_pk PRIMARY KEY (pixel_id, obs_type)
-- );

-- CREATE TABLE vswir_plants.extracted_locations(
--     pixel_id INTEGER NOT NULL,
--     loc_type vswir_plants."LOC_type",
--     loc_value DOUBLE PRECISION,
--     CONSTRAINT extracted_locations_fkey FOREIGN KEY (pixel_id)
--         REFERENCES vswir_plants.pixel(pixel_id)
--         ON DELETE CASCADE,
--     CONSTRAINT extracted_loc_pk PRIMARY KEY (pixel_id, loc_type)
-- );

-- storing radiance as an array of length band number vs one row for every band
-- CREATE TABLE vswir_plants.extracted_spectra (
--     pixel_id INTEGER NOT NULL,
--     band_number INTEGER NOT NULL,
--     radiance DOUBLE PRECISION NOT NULL,
--     CONSTRAINT extracted_spectra_fkey FOREIGN KEY (pixel_id)
--         REFERENCES vswir_plants.pixel(pixel_id)
--         ON DELETE CASCADE,
--     CONSTRAINT extracted_spectra_pk PRIMARY KEY (pixel_id, band_number)
-- );
-- These indexes will improve query times as this table will have millions of rows
-- CREATE INDEX idx_pixel_id ON extracted_spectra(pixel_id);
-- CREATE INDEX idx_band_number ON extracted_spectra(band_number);
-- CREATE INDEX idx_pixel_band ON extracted_spectra(pixel_id, band_number); 
-- this might be faster if it is a composite index
-- range partioning on band number is also an option, but I think only if you are querying by band number adding pixels_id to the query will make it slow

-- -- storing as an array 
-- CREATE TABLE vswir_plants.sensor_campaign_metadata (
--     campaign_name VARCHAR NOT NULL,
--     sensor_name vswir_plants."Sensor_name" NOT NULL,
--     band_number INTEGER,
--     wavelength_center DOUBLE PRECISION,
--     fwhm DOUBLE PRECISION,
--     CONSTRAINT sensor_campaign_metadata_fkey FOREIGN KEY (campaign_name, sensor_name) 
--         REFERENCES vswir_plants.sensor_campaign(campaign_name, sensor_name)
--         ON DELETE CASCADE,
--     CONSTRAINT sensor_campaign_metadata_pk PRIMARY KEY (campaign_name, sensor_name, band_number)
-- );