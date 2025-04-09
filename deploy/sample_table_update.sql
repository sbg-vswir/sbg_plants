-- Deploy sbgplants:sample_table_update to pg

BEGIN;

----- Drop Constraints starting with fkeys

ALTER TABLE IF EXISTS sbgplants.leaf_properties
  DROP CONSTRAINT IF EXISTS leaf_properties_sample_id_fkey;

ALTER TABLE sbgplants.sample_list
  DROP CONSTRAINT "sample_list_pkey";

--- set up new pk column
ALTER TABLE sbgplants.sample_list
    DROP COLUMN sample_id;

ALTER TABLE sbgplants.sample_list
    ADD COLUMN sample_id UUID;

-- recreate pk constraint
ALTER TABLE sbgplants.sample_list
  ADD CONSTRAINT "sample_list_pkey" PRIMARY KEY (sample_id);

-- set up auto gen
ALTER TABLE sbgplants.sample_list
  ALTER COLUMN sample_id SET DEFAULT gen_random_uuid();

------ Update foreign keys

-- set up new fk column

ALTER TABLE sbgplants.leaf_properties
    DROP COLUMN sample_id;

ALTER TABLE sbgplants.leaf_properties
    ADD COLUMN sample_id UUID;

-- Recreate the fk constraint using the updated column 
ALTER TABLE IF EXISTS sbgplants.leaf_properties
  ADD CONSTRAINT leaf_properties_sample_id_fkey FOREIGN KEY (sample_id)
  REFERENCES sbgplants.sample_list (sample_id)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;
-------------------------------

COMMIT;
