-- multiple taxa_systems, varchar array or list multiple in the one column
CREATE TABLE vswir_plants.campaign (
    campaign_name VARCHAR PRIMARY KEY,
    primary_funding_source VARCHAR NOT NULL,
    data_repository vswir_plants."Repository",
    doi VARCHAR,
    taxa_system VARCHAR
);

-- doi table, neon dois change on a yearly basis
-- one campaign many dois
-- what level do we integrate dois, campaign, trait etc
CREATE TABLE vswir_plants.doi (
    campaign_name VARCHAR PRIMARY KEY,
    doi VARCHAR,
    CONSTRAINT doi_campaign_key FOREIGN KEY (campaign_name)
        REFERENCES vswir_plants.campaign(campaign_name)
        ON DELETE CASCADE,
    CONSTRAINT sensor_campaign_pk PRIMARY KEY (doi)
);

-- elevation source does it need a version?
-- add a column(s) for isofit configs either the file name or the s3 path
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

-- a column to specify map space and raw space
-- switch cloud condtion columns to use percentage and translate neon data to use that
-- confidence on alignment column, categorical so this would require an enum
-- remove raster_epsg everything has to be wgs 84/ epsg 4326
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

-- Switch plot shape geom to be Geometry 4326

-- look into performance considerations how would this work with the index
-- I did not see any reason this would impact performance

-- look at the database_api backend to see how the queries are done and if there is performance considerations
-- I believe this would work with the current database_api
-- 1 plot can have many shapes?  1 plot event can have 1 shape? should we try to bring a key here to force a stronger uniquess constraint
CREATE TABLE vswir_plants.plot_shape ( 
    plot_shape_id SERIAL PRIMARY KEY,
    geom geometry(GEOMETRY, 4326) NOT NULL 
    -- geom geometry(POLYGON, 4326) NOT NULL 
);
    
CREATE INDEX plot_shape_idx ON vswir_plants.plot_shape USING GIST (geom);

-- A plot granule combo can have only 1 shape?, we would maybe need to add
-- plot_shape_id to pk if a plot granule can have more than 1 shape
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

-- not all data might have the glt row and column??
-- how do we want to store coords here? should we use do a geometry column to enforce crs?
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
    cosine_i FLOAT4 NOT NULL,
    raw_cosine_i FLOAT4, -- needs to be not null in the future?
    lon FLOAT4 NOT NULL, 
    lat FLOAT4 NOT NULL,
    elevation FLOAT4 NOT NULL,
    CONSTRAINT pixel_fkey FOREIGN KEY (plot_id, granule_id)
        REFERENCES vswir_plants.plot_raster_intersect(plot_id, granule_id)
        ON DELETE CASCADE
);
CREATE UNIQUE INDEX pixel_idx ON vswir_plants.pixel (plot_id, granule_id, glt_row, glt_column);


-- should I merge this into the pixel table?
CREATE TABLE vswir_plants.extracted_spectra (
    pixel_id INTEGER NOT NULL,
    radiance FLOAT4[], 
    CONSTRAINT extracted_spectra_fkey FOREIGN KEY (pixel_id)
        REFERENCES vswir_plants.pixel(pixel_id)
        ON DELETE CASCADE,
    CONSTRAINT extracted_spectra_pk PRIMARY KEY (pixel_id)
);

-- support other types of outputs, cwc 
-- change name to output_pixel_data_products?
-- include reflectance
CREATE TABLE vswir_plants.output_pixel_data_products (
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
    -- uncertainty_ref FLOAT4[] NOT NULL, dropped for now
    CONSTRAINT output_pixel_rfl_pixel_fkey FOREIGN KEY (pixel_id)
        REFERENCES vswir_plants.pixel(pixel_id) 
        ON DELETE CASCADE
);

CREATE TABLE vswir_plants.insitu_plot_event (
    plot_id INTEGER NOT NULL,
    collection_date DATE NOT NULL,
    plot_veg_type vswir_plants."VEGETATION_type" NOT NULL,
    subplot_cover_method vswir_plants."SUBPLOT_cover_method" NOT NULL,
    floristic_survey BOOLEAN NOT NULL,
    CONSTRAINT insitu_plot_event_plot_fkey FOREIGN KEY (plot_id)
        REFERENCES vswir_plants.plot(plot_id) 
        ON DELETE CASCADE,
    CONSTRAINT insitu_plot_event_pk PRIMARY KEY (plot_id, collection_date)
);

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
    canopy_position vswir_plants."CANOPY_position" NOT NULL,
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
    doi VARCHAR, 
    CONSTRAINT sample_table_fkey FOREIGN KEY (plot_id, collection_date, sample_name)
        REFERENCES vswir_plants.sample (plot_id, collection_date, sample_name)
        ON DELETE CASCADE,
    CONSTRAINT leaf_trait_protocol_key FOREIGN KEY (doi)
        REFERENCES vswir_plants.doi (doi)
        ON DELETE CASCADE,
    CONSTRAINT leaf_trait_pk PRIMARY KEY (plot_id, collection_date, sample_name, trait)
);

-- move things from traits to trait protocols?
-- make a seperate table for trait methods which have protocols, this could be linked to the doi table??
-- link back to the trait table
CREATE TABLE vswir_plants.leaf_trait_protocols (
    doi VARCHAR,
    CONSTRAINT leaf_trait_protocol_doi_key FOREIGN KEY (doi)
        REFERENCES vswir_plants.doi(doi)
        ON DELETE CASCADE,
    CONSTRAINT sensor_campaign_pk PRIMARY KEY(doi)
);