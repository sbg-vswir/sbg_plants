-- Deploy sbgplants:extracted_observations_table_update to pg

BEGIN;

----- Alter the primary key of the table

ALTER TABLE sbgplants.extracted_observations
  DROP CONSTRAINT "extracted_observations_pkey";

ALTER TABLE sbgplants.extracted_observations
    DROP COLUMN obs_id;

ALTER TABLE sbgplants.extracted_observations
    ADD COLUMN obs_id UUID;

ALTER TABLE sbgplants.extracted_observations
  ADD CONSTRAINT "extracted_observations_pkey" PRIMARY KEY (obs_id);

ALTER TABLE sbgplants.extracted_observations
  ALTER COLUMN obs_id SET DEFAULT gen_random_uuid();

COMMIT;
