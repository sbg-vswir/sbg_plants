-- Deploy sbgplants:sbg_plants_v1 to pg

BEGIN;

-- Type: FRACTIONAL_class

-- DROP TYPE IF EXISTS sbgplants."FRACTIONAL_class";

CREATE TYPE sbgplants."FRACTIONAL_class" AS ENUM
    ('pv', 'npv', 'soil', 'water', 'char', 'snow');

-- ALTER TYPE sbgplants."FRACTIONAL_class"
--     OWNER TO postgres;
-------------------------------------------------------------
-- Type: FRACTIONAL_method

-- DROP TYPE IF EXISTS sbgplants."FRACTIONAL_method";

CREATE TYPE sbgplants."FRACTIONAL_method" AS ENUM
    ('Point', 'Line-intercept-transect', 'Quadrat');

-- ALTER TYPE sbgplants."FRACTIONAL_method"
--     OWNER TO postgres;
-------------------------------------------------------------
-- Type: OBS_type

-- DROP TYPE IF EXISTS sbgplants."OBS_type";

CREATE TYPE sbgplants."OBS_type" AS ENUM
    ('path length', 'to-sensor-azimuth', 'to-sensor-zenith', 'to-sun-azimuth', 'to-sun-zenith', 'solar phase', 'slope', 'aspect', 'cosine i', 'UTC time');

-- ALTER TYPE sbgplants."OBS_type"
--     OWNER TO postgres;

COMMENT ON TYPE sbgplants."OBS_type"
    IS 'List of observation parameters from OBS file';
-------------------------------------------------------------
-- Type: PLOT_type

-- DROP TYPE IF EXISTS sbgplants."PLOT_type";

CREATE TYPE sbgplants."PLOT_type" AS ENUM
    ('Individual', 'Transect', 'Plot');

-- ALTER TYPE sbgplants."PLOT_type"
--     OWNER TO postgres;

-------------------------------------------------------------
-- Type: Repository

-- DROP TYPE IF EXISTS sbgplants."Repository";

CREATE TYPE sbgplants."Repository" AS ENUM
    ('ORNL DAAC', 'NEON', 'ECOSIS');

-- ALTER TYPE sbgplants."Repository"
--     OWNER TO postgres;
-------------------------------------------------------------
-- Type: Sample_handling

-- DROP TYPE IF EXISTS sbgplants."Sample_handling";

CREATE TYPE sbgplants."Sample_handling" AS ENUM
    ('Fresh', 'Flash frozen', 'Oven dried');

-- ALTER TYPE sbgplants."Sample_handling"
--     OWNER TO postgres;
-------------------------------------------------------------
-- Type: Trait

-- DROP TYPE IF EXISTS sbgplants."Trait";

CREATE TYPE sbgplants."Trait" AS ENUM
    ('wet weight', 'dry weight', 'LWC', 'CRF', 'Chl', 'LMA', 'LAI', 'Nitrogen', 'Phosphorus', 'Magnesium', 'Potassium', 'Calcium', 'Sulfur', 'Boron', 'Iron', 'Manganese', 'Copper', 'Zinc', 'Aluminum', 'Sodium');

-- ALTER TYPE sbgplants."Trait"
--     OWNER TO postgres;
-------------------------------------------------------------
-- Type: Trait_method

-- DROP TYPE IF EXISTS sbgplants."Trait_method";

CREATE TYPE sbgplants."Trait_method" AS ENUM
    ('Destructive', 'Non-destructive');

-- ALTER TYPE sbgplants."Trait_method"
--     OWNER TO postgres;
-------------------------------------------------------------
-- Type: Trait_units

-- DROP TYPE IF EXISTS sbgplants."Trait_units";

CREATE TYPE sbgplants."Trait_units" AS ENUM
    ('g', 'percentage', 'ratio', 'mg m-2', 'grams dry mass per g m2', 'concentration in percent dry mass', 'concentration in ppm');

-- ALTER TYPE sbgplants."Trait_units"
--     OWNER TO postgres;


----------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sbgplants.spatial_ref_sys
(
    srid integer NOT NULL,
    auth_name character varying(256) COLLATE pg_catalog."default",
    auth_srid integer,
    srtext character varying(2048) COLLATE pg_catalog."default",
    proj4text character varying(2048) COLLATE pg_catalog."default",
    CONSTRAINT spatial_ref_sys_pkey PRIMARY KEY (srid)
);

CREATE TABLE IF NOT EXISTS sbgplants.plot
(
    plot_name character(20) NOT NULL,
    plot_type "PLOT_type",
    campaign character(25),
    CONSTRAINT "shift_plot_PK" PRIMARY KEY (plot_name),
    UNIQUE (plot_name)
);

COMMENT ON TABLE sbgplants.plot
    IS 'Contains plot information and summaries of the vegetation survey results within that plot.

plot_type: PLOT_type type';

CREATE TABLE IF NOT EXISTS sbgplants.raster_plot_event
(
    plot_event_id integer NOT NULL,
    plot_name character(20) NOT NULL,
    sample_date date NOT NULL,
    geom geometry (POLYGON, 4326),
    flightline_id character(250) NOT NULL,
    scene_id character(250) NOT NULL,
    acquisition_date date,
    extraction_method character,
    CONSTRAINT "plot_event_ID" PRIMARY KEY (plot_event_id),
    UNIQUE (plot_event_id)
        INCLUDE(plot_name)
);

COMMENT ON TABLE sbgplants.raster_plot_event
    IS 'Plot delineations (polygon)';

CREATE TABLE IF NOT EXISTS sbgplants.plot_event_metadata
(
    plot_event_id integer NOT NULL,
    plot_name character(20) NOT NULL,
    plot_type character NOT NULL,
    team character(15),
    collection_date date NOT NULL,
    latitude double precision,
    longitude double precision,
    gps_plot_orientation character(20),
    gps_accuracy_approx double precision,
    fractional_cover_method "FRACTIONAL_method",
    plot_cover_photos boolean,
    floristic_survey boolean,
    notes character(250),
    PRIMARY KEY (plot_event_id),
    UNIQUE (plot_event_id)
);

COMMENT ON TABLE sbgplants.plot_event_metadata
    IS 'Contains metadata associated to each plot.';

CREATE TABLE IF NOT EXISTS sbgplants.sample_list
(
    sample_id character(50) NOT NULL,
    sample_name character(50) NOT NULL,
    plot_event_id integer NOT NULL,
    plot_name character(20) NOT NULL,
    campaign_id character(50) NOT NULL,
    species_id character(25) NOT NULL,
    phenophase character NOT NULL,
    sample_fractional_cover "FRACTIONAL_class" NOT NULL,
    sample_fract_cover_method "FRACTIONAL_method" NOT NULL,
    understory boolean NOT NULL,
    fractional_cover_understory numrange,
    notes character(250),
    PRIMARY KEY (sample_id),
    UNIQUE (sample_id)
);

COMMENT ON TABLE sbgplants.sample_list
    IS 'Contains information related to sampled plants.

sample_fract_cover_method: FRACTIONAL_method type';

CREATE TABLE IF NOT EXISTS sbgplants.species_list
(
    species_id character(25) NOT NULL,
    species_or_type character(50),
    lifeform_code integer,
    native_spp boolean,
    species_genus_type character,
    PRIMARY KEY (species_id),
    UNIQUE (species_id),
    UNIQUE (species_or_type)
);

CREATE TABLE IF NOT EXISTS sbgplants.flightline
(
    flightline_id character(25) NOT NULL,
    sensor_camp_id character(250) NOT NULL,
    acquisition_time time with time zone NOT NULL,
    acquisition_date date NOT NULL,
    doi_url character(250),
    cloudy_conditions boolean,
    PRIMARY KEY (flightline_id),
    UNIQUE (flightline_id)
        INCLUDE(flightline_id)
);

CREATE TABLE IF NOT EXISTS sbgplants.extracted_spectra
(
    extract_id integer NOT NULL,
    pixel_id integer NOT NULL,
    band_number integer,
    radiance double precision,
    reflectance double precision,
    uncertainty_ref double precision,
    PRIMARY KEY (extract_id),
    UNIQUE (extract_id)
);

CREATE TABLE IF NOT EXISTS sbgplants.insitu_plot_event
(
    insitu_plot_id integer NOT NULL,
    collection_date date NOT NULL,
    plot_name character(25) NOT NULL,
    geom geometry (POLYGON, 4326),
    PRIMARY KEY (insitu_plot_id),
    UNIQUE (insitu_plot_id)
);

COMMENT ON TABLE sbgplants.insitu_plot_event
    IS 'polygon';

CREATE TABLE IF NOT EXISTS sbgplants.sensor_campaign
(
    sensor_camp_id character NOT NULL,
    band_number integer,
    wavelenght_center double precision,
    fwhm double precision,
    PRIMARY KEY (sensor_camp_id)
);

CREATE TABLE IF NOT EXISTS sbgplants.pixel
(
    pixel_id integer NOT NULL,
    plot_name character(20) NOT NULL,
    flightline_id character NOT NULL,
    scene_id character NOT NULL,
    glt_row integer,
    glt_column integer,
    PRIMARY KEY (pixel_id),
    UNIQUE (pixel_id)
);

CREATE TABLE IF NOT EXISTS sbgplants.extracted_observations
(
    obs_id integer NOT NULL,
    pixel_id integer NOT NULL,
    obs_type "OBS_type",
    obs_value double precision,
    PRIMARY KEY (obs_id),
    UNIQUE (obs_id)
);

COMMENT ON TABLE sbgplants.extracted_observations
    IS 'Observation data associated to extracted pixels

obs_type: OBS_type';

CREATE TABLE IF NOT EXISTS sbgplants.scene
(
    scene_id character(25) NOT NULL,
    sensor_camp_id character(250) NOT NULL,
    acquisition_date date NOT NULL,
    doi_url character(250),
    PRIMARY KEY (scene_id),
    UNIQUE (scene_id)
);

CREATE TABLE IF NOT EXISTS sbgplants.fractional_cover
(
    fract_cover_id integer NOT NULL,
    plot_event_id integer NOT NULL,
    fc_class "FRACTIONAL_class" NOT NULL,
    fc_percentage double precision NOT NULL,
    PRIMARY KEY (fract_cover_id),
    UNIQUE (fract_cover_id)
);

COMMENT ON TABLE sbgplants.fractional_cover
    IS 'fc_class : FRACTIONAL_class type';

CREATE TABLE IF NOT EXISTS sbgplants.campaign
(
    campaign_id character(50) NOT NULL,
    name character(50) NOT NULL,
    primary_founding_agency character(50) NOT NULL,
    data_repository "Repository",
    doy character(250),
    PRIMARY KEY (campaign_id),
    UNIQUE (campaign_id)
);

COMMENT ON TABLE sbgplants.campaign
    IS 'data_repository: Reposiroty type';

CREATE TABLE IF NOT EXISTS sbgplants.leaf_properties
(
    trait_id integer NOT NULL,
    sample_id character(50) NOT NULL,
    trait "Trait" NOT NULL,
    value double precision NOT NULL,
    error_precision character,
    method "Trait_method" NOT NULL,
    handling "Sample_handling" NOT NULL,
    units "Trait_units" NOT NULL,
    notes character(250),
    PRIMARY KEY (trait_id),
    UNIQUE (trait_id)
);

COMMENT ON TABLE sbgplants.leaf_properties
    IS 'trait: Trait type
handling: Sample_handling type
method: Trait_method type
units: Trait_units type';

ALTER TABLE IF EXISTS sbgplants.raster_plot_event
    ADD FOREIGN KEY (flightline_id)
    REFERENCES sbgplants.flightline (flightline_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.raster_plot_event
    ADD FOREIGN KEY (scene_id)
    REFERENCES sbgplants.scene (scene_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.plot_event_metadata
    ADD FOREIGN KEY (plot_name)
    REFERENCES sbgplants.plot (plot_name) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.plot_event_metadata
    ADD FOREIGN KEY (plot_event_id)
    REFERENCES sbgplants.raster_plot_event (plot_event_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.sample_list
    ADD FOREIGN KEY (plot_event_id)
    REFERENCES sbgplants.raster_plot_event (plot_event_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.sample_list
    ADD FOREIGN KEY (plot_name)
    REFERENCES sbgplants.plot (plot_name) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.sample_list
    ADD FOREIGN KEY (campaign_id)
    REFERENCES sbgplants.campaign (campaign_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.sample_list
    ADD FOREIGN KEY (species_id)
    REFERENCES sbgplants.species_list (species_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.flightline
    ADD FOREIGN KEY (sensor_camp_id)
    REFERENCES sbgplants.sensor_campaign (sensor_camp_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.extracted_spectra
    ADD FOREIGN KEY (pixel_id)
    REFERENCES sbgplants.pixel (pixel_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.insitu_plot_event
    ADD FOREIGN KEY (plot_name)
    REFERENCES sbgplants.plot (plot_name) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.pixel
    ADD FOREIGN KEY (plot_name)
    REFERENCES sbgplants.plot (plot_name) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.pixel
    ADD FOREIGN KEY (flightline_id)
    REFERENCES sbgplants.flightline (flightline_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.pixel
    ADD FOREIGN KEY (scene_id)
    REFERENCES sbgplants.scene (scene_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.extracted_observations
    ADD FOREIGN KEY (pixel_id)
    REFERENCES sbgplants.pixel (pixel_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.scene
    ADD FOREIGN KEY (sensor_camp_id)
    REFERENCES sbgplants.sensor_campaign (sensor_camp_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.fractional_cover
    ADD FOREIGN KEY (plot_event_id)
    REFERENCES sbgplants.plot_event_metadata (plot_event_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;


ALTER TABLE IF EXISTS sbgplants.leaf_properties
    ADD FOREIGN KEY (sample_id)
    REFERENCES sbgplants.sample_list (sample_id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION
    NOT VALID;

COMMIT;
