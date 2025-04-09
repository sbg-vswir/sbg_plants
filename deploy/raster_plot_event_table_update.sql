-- Deploy sbgplants:raster_plot_event_table_update to pg

BEGIN;

-- Drop constraints
ALTER TABLE IF EXISTS sbgplants.plot_event_metadata
  DROP CONSTRAINT IF EXISTS plot_event_metadata_plot_event_id_fkey;

ALTER TABLE IF EXISTS sbgplants.sample_list
  DROP CONSTRAINT IF EXISTS sample_list_plot_event_id_fkey;

ALTER TABLE IF EXISTS sbgplants.fractional_cover
  DROP CONSTRAINT IF EXISTS fractional_cover_plot_event_id_fkey;

ALTER TABLE sbgplants.raster_plot_event
  DROP CONSTRAINT "plot_event_ID";

-- set up new pk column
ALTER TABLE sbgplants.raster_plot_event
    DROP COLUMN plot_event_id;

ALTER TABLE sbgplants.raster_plot_event
    ADD COLUMN raster_plot_event_id UUID;

-- recreate the primary key constraint with new column/name/datatype
ALTER TABLE sbgplants.raster_plot_event
  ADD CONSTRAINT "raster_plot_event_id" PRIMARY KEY (raster_plot_event_id);

ALTER TABLE sbgplants.raster_plot_event
  ALTER COLUMN raster_plot_event_id SET DEFAULT gen_random_uuid();

------ Update foreign keys

-- Add the new columns to the tables which used plot_event_id as a fkey

ALTER TABLE sbgplants.plot_event_metadata
  ADD COLUMN raster_plot_event_id UUID;

ALTER TABLE sbgplants.plot_event_metadata
    DROP COLUMN plot_event_id;

ALTER TABLE sbgplants.sample_list
  ADD COLUMN raster_plot_event_id UUID;

ALTER TABLE sbgplants.sample_list
    DROP COLUMN plot_event_id;

ALTER TABLE sbgplants.fractional_cover
  ADD COLUMN raster_plot_event_id UUID;

ALTER TABLE sbgplants.fractional_cover
    DROP COLUMN plot_event_id;

-- Recreate the fk constraint using the updated column 
ALTER TABLE IF EXISTS sbgplants.plot_event_metadata
  ADD CONSTRAINT plot_event_metadata_raster_plot_event_id_fkey FOREIGN KEY (raster_plot_event_id)
  REFERENCES sbgplants.raster_plot_event (raster_plot_event_id)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

ALTER TABLE IF EXISTS sbgplants.sample_list
  ADD CONSTRAINT sample_list_raster_plot_event_id_fkey FOREIGN KEY (raster_plot_event_id)
  REFERENCES sbgplants.raster_plot_event (raster_plot_event_id)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

ALTER TABLE IF EXISTS sbgplants.fractional_cover
  ADD CONSTRAINT fractional_cover_raster_plot_event_id_fkey FOREIGN KEY (raster_plot_event_id)
  REFERENCES sbgplants.raster_plot_event (raster_plot_event_id)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

-------------------------------

COMMIT;
