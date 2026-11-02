"""
Promotion transaction — copies data from vswir_plants_staging to vswir_plants
in dependency order.

Staged plot / plot_shape / pixel rows already carry their production ids (the
staging tables take them from the production sequences), and child rows
already point at the right production parent — new in this batch or already
in production. So every table is a straight INSERT … SELECT with explicit
ids; nothing is remapped. Rows QAQC found already in production (reused) were
never staged, so they aren't inserted again.

campaign_name is VARCHAR in staging and the CAMPAIGN_name enum in production,
hence the casts.
"""

import logging
import psycopg2.errors

logger = logging.getLogger(__name__)

STAGING_TABLES = [
    "extracted_spectra", "pixel", "leaf_traits", "sample",
    "insitu_plot_event", "plot_raster_intersect", "plot",
    "plot_shape", "granule", "sensor_campaign", "doi", "campaign",
]

CAMPAIGN = 'campaign_name::vswir_plants."CAMPAIGN_name"'

# (table, production columns, SELECT expressions from staging) in dependency order
PROMOTIONS = [
    ("campaign",
     "campaign_name, primary_funding_source, data_repository, taxa_system",
     f"{CAMPAIGN}, primary_funding_source, data_repository, taxa_system"),
    ("sensor_campaign",
     "campaign_name, sensor_name, sensor_date, elevation_source, wavelength_center, fwhm",
     f"{CAMPAIGN}, sensor_name, sensor_date, elevation_source, wavelength_center, fwhm"),
    ("doi",
     "campaign_name, doi, citation_text, role, sensor_name, plot_method, trait_method, trait, site_ids",
     f"{CAMPAIGN}, doi, citation_text, role, sensor_name, plot_method, trait_method, trait, site_ids"),
    ("granule",
     "granule_id, campaign_name, sensor_name, sensor_date, acquisition_start_time, acquisition_date, "
     "granule_rad_url, granule_refl_url, flightline_id, cloudy_conditions, cloud_type, gsd, raster_epsg",
     f"granule_id, {CAMPAIGN}, sensor_name, sensor_date, acquisition_start_time, acquisition_date, "
     "granule_rad_url, granule_refl_url, flightline_id, cloudy_conditions, cloud_type, gsd, raster_epsg"),
    ("plot_shape",
     "plot_shape_id, geom",
     "plot_shape_id, geom"),
    ("plot",
     "plot_id, campaign_name, site_id, plot_name, plot_method",
     f"plot_id, {CAMPAIGN}, site_id, plot_name, plot_method"),
    ("plot_raster_intersect",
     "plot_id, granule_id, plot_shape_id, extraction_method, delineation_method, "
     "shape_aligned_to_granule, polygon_confidence",
     "plot_id, granule_id, plot_shape_id, extraction_method, delineation_method, "
     "shape_aligned_to_granule, polygon_confidence"),
    ("insitu_plot_event",
     "plot_id, collection_date, plot_veg_type, subplot_cover_method, floristic_survey",
     "plot_id, collection_date, plot_veg_type, subplot_cover_method, floristic_survey"),
    ("sample",
     "plot_id, collection_date, sample_name, taxa, veg_or_cover_type, phenophase, "
     "sample_fc_class, sample_fc_percent, plant_status, canopy_position",
     "plot_id, collection_date, sample_name, taxa, veg_or_cover_type, phenophase, "
     "sample_fc_class, sample_fc_percent, plant_status, canopy_position"),
    # trait_id is left to the production SERIAL — nothing references it
    ("leaf_traits",
     "plot_id, collection_date, sample_name, trait, value, method, handling, units, error, error_type",
     "plot_id, collection_date, sample_name, trait, value, method, handling, units, error, error_type"),
    ("pixel",
     "pixel_id, plot_id, granule_id, glt_row, glt_column, shade_mask, path_length, "
     "to_sensor_azimuth, to_sensor_zenith, to_sun_azimuth, to_sun_zenith, solar_phase, "
     "slope, aspect, utc_time, cosine_i, lon, lat, elevation",
     "pixel_id, plot_id, granule_id, glt_row, glt_column, shade_mask, path_length, "
     "to_sensor_azimuth, to_sensor_zenith, to_sun_azimuth, to_sun_zenith, solar_phase, "
     "slope, aspect, utc_time, cosine_i, lon, lat, elevation"),
    ("extracted_spectra",
     "pixel_id, radiance",
     "pixel_id, radiance"),
]


def promote(conn, batch_id: str):
    """
    Run the full promotion in a single transaction.
    Commits on success. Rolls back on failure — staging data preserved.
    """
    with conn:
        for table, prod_cols, select_cols in PROMOTIONS:
            count = _promote_table(conn, batch_id, table, prod_cols, select_cols)
            logger.info("Promoted %d row(s) into %s", count, table)

        logger.info("Refreshing plot_pixels_mv")
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY vswir_plants.plot_pixels_mv")

        logger.info("Cleaning up staging")
        _cleanup_staging(conn, batch_id)


def _promote_table(conn, batch_id: str, table: str, prod_cols: str, select_cols: str) -> int:
    """
    INSERT … SELECT one table's rows for this batch. A unique violation means
    another batch added the same row after this one passed QAQC (QAQC can't
    see other staged batches) — the batch needs a recheck, which will then
    reuse or reject that row.
    """
    with conn.cursor() as cur:
        try:
            cur.execute(f"""
                INSERT INTO vswir_plants.{table} ({prod_cols})
                SELECT {select_cols}
                FROM vswir_plants_staging.{table}
                WHERE batch_id = %s
            """, (batch_id,))
        except psycopg2.errors.UniqueViolation as e:
            raise RuntimeError(
                f"{table}: a row in this batch was added to production by another batch "
                f"since this one passed QAQC — recheck the batch. ({e.diag.message_detail})"
            ) from e
        return cur.rowcount


def _cleanup_staging(conn, batch_id: str):
    with conn.cursor() as cur:
        for table in STAGING_TABLES:
            cur.execute(
                f"DELETE FROM vswir_plants_staging.{table} WHERE batch_id = %s",
                (batch_id,)
            )
            logger.info("Deleted staging.%s for batch_id=%s", table, batch_id)
