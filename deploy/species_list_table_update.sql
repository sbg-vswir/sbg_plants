-- Deploy sbgplants:species_list_table_update to pg

BEGIN;

----- Drop constraints

ALTER TABLE IF EXISTS sbgplants.sample_list
  DROP CONSTRAINT IF EXISTS "sample_list_species_id_fkey";

ALTER TABLE sbgplants.species_list
  DROP CONSTRAINT "species_list_pkey";

ALTER TABLE sbgplants.species_list
  DROP CONSTRAINT IF EXISTS "species_list_species_or_type_key";

-- create new pk constraint
ALTER TABLE sbgplants.species_list
  ADD CONSTRAINT "species_or_type_pkey" PRIMARY KEY (species_or_type);

-- remove unneeded old pk column
ALTER TABLE sbgplants.species_list
   DROP COLUMN IF EXISTS species_id;

------ Update foreign keys

-- Drop existing fk constraint

ALTER TABLE sbgplants.sample_list
   DROP COLUMN IF EXISTS species_id;

ALTER TABLE sbgplants.sample_list
  ADD COLUMN IF NOT EXISTS species_or_type character(50);

ALTER TABLE IF EXISTS sbgplants.sample_list
  ADD CONSTRAINT "sample_list_species_or_type_fkey" FOREIGN KEY (species_or_type)
  REFERENCES sbgplants.species_list (species_or_type)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

COMMIT;
