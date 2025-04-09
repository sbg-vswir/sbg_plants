-- Deploy sbgplants:flightline_table_update to pg

BEGIN;

-- Drop constraints
ALTER TABLE IF EXISTS sbgplants.raster_plot_event
  DROP CONSTRAINT IF EXISTS raster_plot_event_flightline_id_fkey;

ALTER TABLE IF EXISTS sbgplants.pixel
  DROP CONSTRAINT IF EXISTS pixel_flightline_id_fkey;

ALTER TABLE sbgplants.flightline
  DROP CONSTRAINT "flightline_pkey";

-- set up the new pk column
ALTER TABLE sbgplants.flightline
    DROP COLUMN flightline_id;

ALTER TABLE sbgplants.flightline
    ADD COLUMN flightline_id UUID;

-- create new pk constraint
ALTER TABLE sbgplants.flightline
  ADD CONSTRAINT "flightline_pkey" PRIMARY KEY (flightline_id);

ALTER TABLE sbgplants.flightline
  ALTER COLUMN flightline_id SET DEFAULT gen_random_uuid();

-- change column in fk tables
ALTER TABLE sbgplants.raster_plot_event
    DROP COLUMN flightline_id;

ALTER TABLE sbgplants.raster_plot_event
    ADD COLUMN flightline_id UUID;

ALTER TABLE sbgplants.pixel
    DROP COLUMN flightline_id;

ALTER TABLE sbgplants.pixel
    ADD COLUMN flightline_id UUID;

-- Recreate the fk constraint using the updated column 
ALTER TABLE IF EXISTS sbgplants.raster_plot_event
  ADD CONSTRAINT raster_plot_event_flightline_id_fkey FOREIGN KEY (flightline_id)
  REFERENCES sbgplants.flightline (flightline_id)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

ALTER TABLE IF EXISTS sbgplants.pixel
  ADD CONSTRAINT pixel_flightline_id_fkey FOREIGN KEY (flightline_id)
  REFERENCES sbgplants.flightline (flightline_id)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;
-------------------------------
COMMIT;
