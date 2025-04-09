-- Deploy sbgplants:fractional_cover_table_update to pg

BEGIN;

ALTER TABLE sbgplants.fractional_cover
  DROP CONSTRAINT "fractional_cover_pkey";

ALTER TABLE sbgplants.fractional_cover
    DROP COLUMN fract_cover_id;

ALTER TABLE sbgplants.fractional_cover
  ADD COLUMN fract_cover_id UUID;

ALTER TABLE sbgplants.fractional_cover
  ADD CONSTRAINT "fractional_cover_pkey" PRIMARY KEY (fract_cover_id);

ALTER TABLE sbgplants.fractional_cover
  ALTER COLUMN fract_cover_id SET DEFAULT gen_random_uuid();

COMMIT;
