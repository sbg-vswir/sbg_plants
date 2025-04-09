-- Deploy sbgplants:extracted_spectra_table_update to pg

BEGIN;

----- Alter the primary key of the table
ALTER TABLE sbgplants.extracted_spectra
  DROP CONSTRAINT "extracted_spectra_pkey";

ALTER TABLE sbgplants.extracted_spectra
    DROP COLUMN extract_id;

ALTER TABLE sbgplants.extracted_spectra
    ADD COLUMN extract_id UUID;

ALTER TABLE sbgplants.extracted_spectra
  ADD CONSTRAINT "extracted_spectra_pkey" PRIMARY KEY (extract_id);

ALTER TABLE sbgplants.extracted_spectra
  ALTER COLUMN extract_id SET DEFAULT gen_random_uuid();

COMMIT;