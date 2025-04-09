-- Deploy sbgplants:pixel_table_update to pg

BEGIN;

-- Drop constraints
-- Drop existing fk constraint first
ALTER TABLE IF EXISTS sbgplants.extracted_observations
  DROP CONSTRAINT IF EXISTS extracted_observations_pixel_id_fkey;

ALTER TABLE IF EXISTS sbgplants.extracted_spectra
  DROP CONSTRAINT IF EXISTS extracted_spectra_pixel_id_fkey;

ALTER TABLE sbgplants.pixel
  DROP CONSTRAINT "pixel_pkey";


-- set up the new pk column
ALTER TABLE sbgplants.pixel
    DROP COLUMN pixel_id;

ALTER TABLE sbgplants.pixel
    ADD COLUMN pixel_id UUID;

ALTER TABLE sbgplants.pixel
  ADD CONSTRAINT "pixel_pkey" PRIMARY KEY (pixel_id);

ALTER TABLE sbgplants.pixel
  ALTER COLUMN pixel_id SET DEFAULT gen_random_uuid();

------ Update foreign keys
-- change column in fk tables
ALTER TABLE sbgplants.extracted_observations
    DROP COLUMN pixel_id;

ALTER TABLE sbgplants.extracted_observations
    ADD COLUMN pixel_id UUID;

ALTER TABLE sbgplants.extracted_spectra
    DROP COLUMN pixel_id;

ALTER TABLE sbgplants.extracted_spectra
    ADD COLUMN pixel_id UUID;

-- Recreate the fk constraint using the updated column 
ALTER TABLE IF EXISTS sbgplants.extracted_observations
  ADD CONSTRAINT extracted_spectra_pixel_id_fkey FOREIGN KEY (pixel_id)
  REFERENCES sbgplants.pixel (pixel_id)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

ALTER TABLE IF EXISTS sbgplants.extracted_spectra
  ADD CONSTRAINT extracted_spectra_pixel_id_fkey FOREIGN KEY (pixel_id)
  REFERENCES sbgplants.pixel (pixel_id)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;
-------------------------------

COMMIT;
