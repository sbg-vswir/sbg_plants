-- Deploy sbgplants:plot_table_update to pg

BEGIN;

ALTER TABLE sbgplants.plot
  RENAME CONSTRAINT "shift_plot_PK" TO "plot_name_PK";

COMMIT;
