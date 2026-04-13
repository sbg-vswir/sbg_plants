-- ── vswir_plants_staging tables ──────────────────────────────────────────────
--
-- Mirrors vswir_plants schema with the following differences:
--   1. Schema is vswir_plants_staging instead of vswir_plants
--   2. Every table has a batch_id VARCHAR NOT NULL column
--   3. Foreign keys reference staging tables (not production)
--   4. Serial IDs use staging sequences — thrown away on promotion
--   5. Enum types are reused from vswir_plants schema (same DB, different schema)
--   6. No output tables (output_pixel_fc, output_pixel_rfl) — never ingested
-- ─────────────────────────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS vswir_plants_staging;

-- ── campaign ──────────────────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.campaign (
    campaign_name          VARCHAR                     NOT NULL,
    primary_funding_source VARCHAR                     NOT NULL,
    data_repository        vswir_plants."Repository",
    doi                    VARCHAR,
    taxa_system            VARCHAR,
    batch_id               VARCHAR                     NOT NULL,
    CONSTRAINT staging_campaign_pk PRIMARY KEY (campaign_name, batch_id)
);

-- ── sensor_campaign ───────────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.sensor_campaign (
    campaign_name     VARCHAR                          NOT NULL,
    sensor_name       vswir_plants."Sensor_name"       NOT NULL,
    elevation_source  vswir_plants."ELEVATION_source"  NOT NULL,
    wavelength_center FLOAT4[]                         NOT NULL,
    fwhm              FLOAT4[]                         NOT NULL,
    batch_id          VARCHAR                          NOT NULL,
    CONSTRAINT staging_sensor_campaign_pk PRIMARY KEY (campaign_name, sensor_name, batch_id),
    CONSTRAINT staging_sensor_campaign_fkey FOREIGN KEY (campaign_name, batch_id)
        REFERENCES vswir_plants_staging.campaign(campaign_name, batch_id)
        ON DELETE CASCADE
);

-- ── granule ───────────────────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.granule (
    granule_id             VARCHAR                         NOT NULL,
    campaign_name          VARCHAR                         NOT NULL,
    sensor_name            vswir_plants."Sensor_name"      NOT NULL,
    acquisition_start_time TIME                            NOT NULL,
    acquisition_date       DATE                            NOT NULL,
    granule_rad_url        VARCHAR,
    granule_refl_url       VARCHAR,
    flightline_id          VARCHAR,
    cloudy_conditions      vswir_plants."CLOUD_conditions" NOT NULL,
    cloud_type             vswir_plants."CLOUD_type"       NOT NULL,
    gsd                    FLOAT4                          NOT NULL,
    raster_epsg            INTEGER                         NOT NULL,
    batch_id               VARCHAR                         NOT NULL,
    CONSTRAINT staging_granule_pk PRIMARY KEY (granule_id, batch_id),
    CONSTRAINT staging_granule_fkey FOREIGN KEY (campaign_name, sensor_name, batch_id)
        REFERENCES vswir_plants_staging.sensor_campaign(campaign_name, sensor_name, batch_id)
        ON DELETE CASCADE
);

-- ── plot_shape ────────────────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.plot_shape (
    plot_shape_id SERIAL,
    geom          geometry(POLYGON, 4326) NOT NULL,
    batch_id      VARCHAR                 NOT NULL,
    CONSTRAINT staging_plot_shape_pk PRIMARY KEY (plot_shape_id, batch_id)
);

CREATE INDEX staging_plot_shape_geom_idx
    ON vswir_plants_staging.plot_shape USING GIST (geom);

-- ── plot ──────────────────────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.plot (
    plot_id       SERIAL,
    campaign_name VARCHAR                   NOT NULL,
    site_id       VARCHAR                   NOT NULL,
    plot_name     VARCHAR                   NOT NULL,
    plot_method   vswir_plants."PLOT_method",
    batch_id      VARCHAR                   NOT NULL,
    CONSTRAINT staging_plot_pk PRIMARY KEY (plot_id, batch_id),
    CONSTRAINT staging_plot_campaign_fkey FOREIGN KEY (campaign_name, batch_id)
        REFERENCES vswir_plants_staging.campaign(campaign_name, batch_id)
        ON DELETE CASCADE
);

-- ── plot_raster_intersect ─────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.plot_raster_intersect (
    plot_id                  INTEGER                           NOT NULL,
    granule_id               VARCHAR                           NOT NULL,
    plot_shape_id            INTEGER                           NOT NULL,
    extraction_method        vswir_plants."EXTRACTION_method"  NOT NULL,
    delineation_method       vswir_plants."DELINEATION_method" NOT NULL,
    shape_aligned_to_granule BOOLEAN                           NOT NULL,
    batch_id                 VARCHAR                           NOT NULL,
    CONSTRAINT staging_plot_raster_intersect_pk PRIMARY KEY (plot_id, granule_id, batch_id),
    CONSTRAINT staging_pri_granule_fkey FOREIGN KEY (granule_id, batch_id)
        REFERENCES vswir_plants_staging.granule(granule_id, batch_id)
        ON DELETE CASCADE,
    CONSTRAINT staging_pri_plot_fkey FOREIGN KEY (plot_id, batch_id)
        REFERENCES vswir_plants_staging.plot(plot_id, batch_id)
        ON DELETE CASCADE,
    CONSTRAINT staging_pri_plot_shape_fkey FOREIGN KEY (plot_shape_id, batch_id)
        REFERENCES vswir_plants_staging.plot_shape(plot_shape_id, batch_id)
        ON DELETE CASCADE
);

-- ── pixel ─────────────────────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.pixel (
    pixel_id          SERIAL,
    plot_id           INTEGER NOT NULL,
    granule_id        VARCHAR NOT NULL,
    glt_row           INTEGER NOT NULL,
    glt_column        INTEGER NOT NULL,
    shade_mask        BOOLEAN NOT NULL,
    path_length       FLOAT4  NOT NULL,
    to_sensor_azimuth FLOAT4  NOT NULL,
    to_sensor_zenith  FLOAT4  NOT NULL,
    to_sun_azimuth    FLOAT4  NOT NULL,
    to_sun_zenith     FLOAT4  NOT NULL,
    solar_phase       FLOAT4  NOT NULL,
    slope             FLOAT4  NOT NULL,
    aspect            FLOAT4  NOT NULL,
    utc_time          FLOAT4  NOT NULL,
    cosine_i          FLOAT4,
    raw_cosine_i      FLOAT4,
    lon               FLOAT4  NOT NULL,
    lat               FLOAT4  NOT NULL,
    elevation         FLOAT4  NOT NULL,
    batch_id          VARCHAR NOT NULL,
    CONSTRAINT staging_pixel_pk PRIMARY KEY (pixel_id, batch_id),
    CONSTRAINT staging_pixel_fkey FOREIGN KEY (plot_id, granule_id, batch_id)
        REFERENCES vswir_plants_staging.plot_raster_intersect(plot_id, granule_id, batch_id)
        ON DELETE CASCADE
);

CREATE UNIQUE INDEX staging_pixel_idx
    ON vswir_plants_staging.pixel (plot_id, granule_id, glt_row, glt_column, batch_id);

-- ── extracted_spectra ─────────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.extracted_spectra (
    pixel_id INTEGER NOT NULL,
    radiance FLOAT4[],
    batch_id VARCHAR NOT NULL,
    CONSTRAINT staging_extracted_spectra_pk PRIMARY KEY (pixel_id, batch_id),
    CONSTRAINT staging_extracted_spectra_fkey FOREIGN KEY (pixel_id, batch_id)
        REFERENCES vswir_plants_staging.pixel(pixel_id, batch_id)
        ON DELETE CASCADE
);

-- ── insitu_plot_event ─────────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.insitu_plot_event (
    plot_id              INTEGER                          NOT NULL,
    collection_date      DATE                             NOT NULL,
    plot_veg_type        vswir_plants."VEGETATION_type"  NOT NULL,
    subplot_cover_method vswir_plants."SUBPLOT_cover_method" NOT NULL,
    floristic_survey     BOOLEAN                          NOT NULL,
    batch_id             VARCHAR                          NOT NULL,
    CONSTRAINT staging_insitu_plot_event_pk PRIMARY KEY (plot_id, collection_date, batch_id),
    CONSTRAINT staging_insitu_plot_event_plot_fkey FOREIGN KEY (plot_id, batch_id)
        REFERENCES vswir_plants_staging.plot(plot_id, batch_id)
        ON DELETE CASCADE
);

-- ── sample ────────────────────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.sample (
    collection_date   DATE                           NOT NULL,
    plot_id           INTEGER                        NOT NULL,
    sample_name       VARCHAR                        NOT NULL,
    taxa              vswir_plants."TAXA"            NOT NULL,
    veg_or_cover_type vswir_plants."VEG_or_cover_type" NOT NULL,
    phenophase        vswir_plants."PHENOPHASE"      NOT NULL,
    sample_fc_class   vswir_plants."FRACTIONAL_class" NOT NULL,
    sample_fc_percent INTEGER                        NOT NULL,
    plant_status      vswir_plants."PLANT_status"    NOT NULL,
    canopy_position   vswir_plants."CANOPY_position" NOT NULL,
    batch_id          VARCHAR                        NOT NULL,
    CONSTRAINT staging_sample_pk PRIMARY KEY (plot_id, collection_date, sample_name, batch_id),
    CONSTRAINT staging_sample_event_fkey FOREIGN KEY (plot_id, collection_date, batch_id)
        REFERENCES vswir_plants_staging.insitu_plot_event(plot_id, collection_date, batch_id)
        ON DELETE CASCADE
);

-- ── leaf_traits ───────────────────────────────────────────────────────────────

CREATE TABLE vswir_plants_staging.leaf_traits (
    sample_name     VARCHAR                        NOT NULL,
    plot_id         INTEGER                        NOT NULL,
    collection_date DATE                           NOT NULL,
    trait           vswir_plants."Trait"           NOT NULL,
    value           FLOAT4                         NOT NULL,
    method          vswir_plants."Trait_method"    NOT NULL,
    handling        vswir_plants."Sample_handling" NOT NULL,
    units           vswir_plants."Trait_units"     NOT NULL,
    error           FLOAT4,
    error_type      vswir_plants."Error_type",
    batch_id        VARCHAR                        NOT NULL,
    CONSTRAINT staging_leaf_traits_pk PRIMARY KEY (plot_id, collection_date, sample_name, trait, batch_id),
    CONSTRAINT staging_leaf_traits_sample_fkey FOREIGN KEY (plot_id, collection_date, sample_name, batch_id)
        REFERENCES vswir_plants_staging.sample(plot_id, collection_date, sample_name, batch_id)
        ON DELETE CASCADE
);
