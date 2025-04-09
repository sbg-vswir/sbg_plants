-- Deploy sbgplants:scene_table_update to pg

BEGIN;

----- Drop Constraints starting with fkeys
ALTER TABLE IF EXISTS sbgplants.raster_plot_event
  DROP CONSTRAINT IF EXISTS raster_plot_event_scene_id_fkey;

ALTER TABLE IF EXISTS sbgplants.pixel
  DROP CONSTRAINT IF EXISTS pixel_scene_id_fkey;

ALTER TABLE sbgplants.scene
  DROP CONSTRAINT "scene_pkey";

--- set up new pk column
ALTER TABLE sbgplants.scene
    DROP COLUMN scene_id;

ALTER TABLE sbgplants.scene
    ADD COLUMN scene_id UUID;

-- recreate pk constraint
ALTER TABLE sbgplants.scene
  ADD CONSTRAINT "scene_pkey" PRIMARY KEY (scene_id);

-- set up auto gen
ALTER TABLE sbgplants.scene
  ALTER COLUMN scene_id SET DEFAULT gen_random_uuid();

------ Update foreign keys

-- set up new fk column

ALTER TABLE sbgplants.raster_plot_event
    DROP COLUMN scene_id;

ALTER TABLE sbgplants.raster_plot_event
    ADD COLUMN scene_id UUID;

ALTER TABLE sbgplants.pixel
    DROP COLUMN scene_id;

ALTER TABLE sbgplants.pixel
    ADD COLUMN scene_id UUID;

-- Recreate the fk constraint using the updated column 
ALTER TABLE IF EXISTS sbgplants.raster_plot_event
  ADD CONSTRAINT raster_plot_event_scene_id_fkey FOREIGN KEY (scene_id)
  REFERENCES sbgplants.scene (scene_id)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

ALTER TABLE IF EXISTS sbgplants.pixel
  ADD CONSTRAINT pixel_scene_id_fkey FOREIGN KEY (scene_id)
  REFERENCES sbgplants.scene (scene_id)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;
-------------------------------

COMMIT;
