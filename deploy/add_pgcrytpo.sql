-- Deploy sbgplants:add_pgcrytpo to pg

BEGIN;

-- Add extension for generating UUIDS
CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA sbgplants;

COMMIT;
