-- Deploy sbgplants:campaign_table_update to pg

BEGIN;

----- Alter the primary key of the table
ALTER TABLE sbgplants.campaign
  RENAME COLUMN name TO campaign_name;

ALTER TABLE IF EXISTS sbgplants.sample_list
  DROP CONSTRAINT IF EXISTS "sample_list_campaign_id_fkey";

ALTER TABLE sbgplants.campaign
  DROP CONSTRAINT "campaign_pkey";

ALTER TABLE sbgplants.campaign
  ADD CONSTRAINT "campaign_pkey" PRIMARY KEY (campaign_name);

------ Update foreign keys

-- Drop existing fk constraint

ALTER TABLE sbgplants.sample_list
  ADD COLUMN IF NOT EXISTS campaign_name character(50);

ALTER TABLE IF EXISTS sbgplants.sample_list
  ADD CONSTRAINT "sample_list_campaign_name_fkey" FOREIGN KEY (campaign_name)
  REFERENCES sbgplants.campaign (campaign_name)
  MATCH SIMPLE
  ON UPDATE NO ACTION
  ON DELETE NO ACTION
  NOT VALID;

-- Drop unneeded column
ALTER TABLE sbgplants.campaign
   DROP COLUMN IF EXISTS campaign_id;

ALTER TABLE sbgplants.sample_list
  DROP COLUMN IF EXISTS campaign_id;

COMMIT;
