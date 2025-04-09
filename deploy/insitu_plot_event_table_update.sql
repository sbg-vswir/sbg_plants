-- Deploy sbgplants:insitu_plot_event_table_update to pg

BEGIN;

ALTER TABLE sbgplants.insitu_plot_event
  DROP CONSTRAINT "insitu_plot_event_pkey";

ALTER TABLE sbgplants.insitu_plot_event
    DROP COLUMN insitu_plot_id;

ALTER TABLE sbgplants.insitu_plot_event
    ADD COLUMN insitu_plot_id UUID;

ALTER TABLE sbgplants.insitu_plot_event
  ADD CONSTRAINT "insitu_plot_event_pkey" PRIMARY KEY (insitu_plot_id);

ALTER TABLE sbgplants.insitu_plot_event
  ALTER COLUMN insitu_plot_id SET DEFAULT gen_random_uuid();

COMMIT;
