-- Deploy sbgplants:trait_table_update to pg

BEGIN;

-- Drop constraint
ALTER TABLE sbgplants.leaf_properties
  DROP CONSTRAINT "leaf_properties_pkey";

-- set up new pk column
ALTER TABLE sbgplants.leaf_properties
    DROP COLUMN trait_id;

ALTER TABLE sbgplants.leaf_properties
    ADD COLUMN trait_id UUID;

-- recreate pk constraint
ALTER TABLE sbgplants.leaf_properties
  ADD CONSTRAINT "leaf_properties_pkey" PRIMARY KEY (trait_id);

-- set up auto gen
ALTER TABLE sbgplants.leaf_properties
  ALTER COLUMN trait_id SET DEFAULT gen_random_uuid();

COMMIT;
