"""
Promotion transaction — copies data from vswir_plants_staging to vswir_plants
in dependency order using pandas/geopandas for bulk operations.

Tables with serial IDs (plot_shape, plot, pixel) use execute_values with
RETURNING to capture production-sequence IDs for dependent inserts.
Large tables (pixel, extracted_spectra) use copy_expert for speed.
"""

import io
import logging
import pandas as pd
import geopandas as gpd
import psycopg2.extras
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

logger     = logging.getLogger(__name__)
CHUNK_SIZE = 5000

STAGING_TABLES = [
    "extracted_spectra", "pixel", "leaf_traits", "sample",
    "insitu_plot_event", "plot_raster_intersect", "plot",
    "plot_shape", "granule", "sensor_campaign", "campaign",
]


def promote(conn, batch_id: str):
    """
    Run the full promotion in a single transaction.
    Commits on success. Rolls back on failure — staging data preserved.
    """
    engine = _engine_from_conn(conn)

    with conn:
        logger.info("Promoting campaign + sensor_campaign")
        _promote_campaign(engine, conn, batch_id)

        logger.info("Promoting granule")
        _promote_granule(engine, batch_id)

        logger.info("Promoting plots")
        shape_id_map = _promote_plot_shapes(conn, engine, batch_id)
        plot_id_map  = _promote_plots(conn, batch_id)
        _promote_plot_raster_intersect(engine, batch_id, plot_id_map, shape_id_map)

        logger.info("Promoting traits")
        _promote_insitu_plot_event(engine, batch_id, plot_id_map)
        _promote_sample(engine, batch_id, plot_id_map)
        _promote_leaf_traits(engine, batch_id, plot_id_map)

        logger.info("Promoting pixels + spectra")
        pixel_id_map = _promote_pixels(conn, batch_id, plot_id_map)
        _promote_spectra(conn, batch_id, pixel_id_map)

        logger.info("Refreshing plot_pixels_mv")
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY vswir_plants.plot_pixels_mv")

        logger.info("Cleaning up staging")
        _cleanup_staging(conn, batch_id)


# ── Table promoters ───────────────────────────────────────────────────────────

def _promote_campaign(engine, conn, batch_id: str):
    df = pd.read_sql(
        "SELECT campaign_name, primary_funding_source, data_repository, doi, taxa_system "
        "FROM vswir_plants_staging.campaign WHERE batch_id = %s",
        conn, params=(batch_id,)
    )
    df.to_sql(
        "campaign", engine, schema="vswir_plants",
        if_exists="append", index=False, method="multi",
    )


def _promote_sensor_campaign(conn, batch_id: str):
    """Uses execute_values because wavelength_center/fwhm are FLOAT4[] arrays."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT campaign_name, sensor_name::text, elevation_source::text,
                   wavelength_center, fwhm
            FROM vswir_plants_staging.sensor_campaign
            WHERE batch_id = %s
        """, (batch_id,))
        rows = cur.fetchall()
        psycopg2.extras.execute_values(cur, """
            INSERT INTO vswir_plants.sensor_campaign
                (campaign_name, sensor_name, elevation_source, wavelength_center, fwhm)
            VALUES %s
            ON CONFLICT DO NOTHING
        """, [
            (r[0], r[1], r[2], list(r[3]), list(r[4]))
            for r in rows
        ])


def _promote_granule(engine, batch_id: str):
    # Read from staging — enums are already valid strings, cast on insert via SQLAlchemy
    with engine.connect() as c:
        df = pd.read_sql(
            "SELECT granule_id, campaign_name, sensor_name::text, "
            "acquisition_start_time::text, acquisition_date, granule_rad_url, "
            "granule_refl_url, flightline_id, cloudy_conditions::text, "
            "cloud_type::text, gsd, raster_epsg "
            "FROM vswir_plants_staging.granule WHERE batch_id = %(batch_id)s",
            c, params={"batch_id": batch_id}
        )
    df.to_sql(
        "granule", engine, schema="vswir_plants",
        if_exists="append", index=False, method="multi",
    )


def _promote_plot_shapes(conn, engine, batch_id: str) -> dict:
    """
    Re-insert plot shapes using GeoPandas to get production plot_shape_ids.
    Returns { staging_plot_shape_id: production_plot_shape_id }
    """
    gdf = gpd.read_postgis(
        f"SELECT plot_shape_id, geom FROM vswir_plants_staging.plot_shape WHERE batch_id = '{batch_id}'",
        conn, geom_col="geom"
    )
    staging_ids = gdf["plot_shape_id"].tolist()

    insert_gdf = gdf[["geom"]].copy()
    insert_gdf.to_postgis(
        "plot_shape", engine, schema="vswir_plants",
        if_exists="append", index=False,
    )

    # Fetch the production IDs that were just inserted (last N rows)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT plot_shape_id FROM vswir_plants.plot_shape
            ORDER BY plot_shape_id DESC
            LIMIT %s
        """, (len(staging_ids),))
        prod_ids = [r[0] for r in cur.fetchall()][::-1]  # reverse to match insertion order

    return dict(zip(staging_ids, prod_ids))


def _promote_plots(conn, batch_id: str) -> dict:
    """
    Insert or find existing plots using execute_values with RETURNING.
    Returns { staging_plot_id: production_plot_id }
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT plot_id, campaign_name, site_id, plot_name, plot_method::text
            FROM vswir_plants_staging.plot WHERE batch_id = %s
        """, (batch_id,))
        staging_rows = cur.fetchall()

        results = psycopg2.extras.execute_values(cur, """
            INSERT INTO vswir_plants.plot (campaign_name, site_id, plot_name, plot_method)
            VALUES %s
            ON CONFLICT DO NOTHING
            RETURNING plot_id, campaign_name, plot_name
        """, [(r[1], r[2], r[3], r[4]) for r in staging_rows], fetch=True)

    # Map staging_plot_id → production_plot_id via campaign+plot_name
    prod_map = {(r[1], r[2]): r[0] for r in results}
    return {r[0]: prod_map.get((r[1], r[3])) for r in staging_rows if (r[1], r[3]) in prod_map}


def _promote_plot_raster_intersect(engine, batch_id: str, plot_id_map: dict, shape_id_map: dict):
    with engine.connect() as c:
        df = pd.read_sql(
            "SELECT plot_id, granule_id, plot_shape_id, extraction_method::text, "
            "delineation_method::text, shape_aligned_to_granule "
            "FROM vswir_plants_staging.plot_raster_intersect WHERE batch_id = %(batch_id)s",
            c, params={"batch_id": batch_id}
        )
    df["plot_id"]      = df["plot_id"].map(plot_id_map)
    df["plot_shape_id"] = df["plot_shape_id"].map(shape_id_map)
    df = df.dropna(subset=["plot_id", "plot_shape_id"])
    df.to_sql(
        "plot_raster_intersect", engine, schema="vswir_plants",
        if_exists="append", index=False, method="multi",
    )


def _promote_insitu_plot_event(engine, batch_id: str, plot_id_map: dict):
    with engine.connect() as c:
        df = pd.read_sql(
            "SELECT plot_id, collection_date, plot_veg_type::text, "
            "subplot_cover_method::text, floristic_survey "
            "FROM vswir_plants_staging.insitu_plot_event WHERE batch_id = %(batch_id)s",
            c, params={"batch_id": batch_id}
        )
    df["plot_id"] = df["plot_id"].map(plot_id_map)
    df = df.dropna(subset=["plot_id"])
    df.to_sql(
        "insitu_plot_event", engine, schema="vswir_plants",
        if_exists="append", index=False, method="multi",
    )


def _promote_sample(engine, batch_id: str, plot_id_map: dict):
    with engine.connect() as c:
        df = pd.read_sql(
            "SELECT plot_id, collection_date, sample_name, taxa::text, "
            "veg_or_cover_type::text, phenophase::text, sample_fc_class::text, "
            "sample_fc_percent, plant_status::text, canopy_position::text "
            "FROM vswir_plants_staging.sample WHERE batch_id = %(batch_id)s",
            c, params={"batch_id": batch_id}
        )
    df["plot_id"] = df["plot_id"].map(plot_id_map)
    df = df.dropna(subset=["plot_id"])
    df.to_sql(
        "sample", engine, schema="vswir_plants",
        if_exists="append", index=False, method="multi",
    )


def _promote_leaf_traits(engine, batch_id: str, plot_id_map: dict):
    with engine.connect() as c:
        df = pd.read_sql(
            "SELECT plot_id, collection_date, sample_name, trait::text, value, "
            "method::text, handling::text, units::text, error, error_type::text "
            "FROM vswir_plants_staging.leaf_traits WHERE batch_id = %(batch_id)s",
            c, params={"batch_id": batch_id}
        )
    df["plot_id"] = df["plot_id"].map(plot_id_map)
    df = df.dropna(subset=["plot_id"])
    df.to_sql(
        "leaf_traits", engine, schema="vswir_plants",
        if_exists="append", index=False, method="multi", chunksize=CHUNK_SIZE,
    )


def _promote_pixels(conn, batch_id: str, plot_id_map: dict) -> dict:
    """
    Chunked pixel promotion using copy_expert.
    Returns { staging_pixel_id: production_pixel_id }
    """
    pixel_cols = [
        "plot_id", "granule_id", "glt_row", "glt_column", "shade_mask",
        "path_length", "to_sensor_azimuth", "to_sensor_zenith",
        "to_sun_azimuth", "to_sun_zenith", "solar_phase", "slope", "aspect",
        "utc_time", "cosine_i", "raw_cosine_i", "lon", "lat", "elevation",
    ]
    pixel_id_map = {}
    offset = 0

    while True:
        df = pd.read_sql(
            "SELECT pixel_id, " + ", ".join(pixel_cols) +
            " FROM vswir_plants_staging.pixel WHERE batch_id = %s "
            "ORDER BY pixel_id LIMIT %s OFFSET %s",
            conn, params=(batch_id, CHUNK_SIZE, offset)
        )
        if df.empty:
            break

        staging_pixel_ids = df["pixel_id"].tolist()
        df["plot_id"] = df["plot_id"].map(plot_id_map)
        df = df.dropna(subset=["plot_id"]).drop(columns=["pixel_id"])

        buf = io.StringIO()
        df.to_csv(buf, index=False, header=False, na_rep="\\N")
        buf.seek(0)

        with conn.cursor() as cur:
            cur.copy_expert(f"""
                COPY vswir_plants.pixel ({','.join(df.columns)})
                FROM STDIN WITH (FORMAT CSV, NULL '\\N')
            """, buf)

            # Fetch back the production pixel_ids just inserted
            cur.execute("""
                SELECT pixel_id, plot_id, granule_id, glt_row, glt_column
                FROM vswir_plants.pixel
                ORDER BY pixel_id DESC
                LIMIT %s
            """, (len(df),))
            prod_rows = cur.fetchall()[::-1]

        # Align staging → production ids positionally
        for s_id, prod_row in zip(staging_pixel_ids, prod_rows):
            pixel_id_map[s_id] = prod_row[0]

        offset += CHUNK_SIZE

    return pixel_id_map


def _promote_spectra(conn, batch_id: str, pixel_id_map: dict):
    """Chunked spectra promotion using copy_expert."""
    offset = 0
    while True:
        df = pd.read_sql(
            "SELECT pixel_id, radiance FROM vswir_plants_staging.extracted_spectra "
            "WHERE batch_id = %s ORDER BY pixel_id LIMIT %s OFFSET %s",
            conn, params=(batch_id, CHUNK_SIZE, offset)
        )
        if df.empty:
            break

        df["pixel_id"] = df["pixel_id"].map(pixel_id_map)
        df = df.dropna(subset=["pixel_id"])

        # Format radiance arrays as Postgres array literals
        rows = [
            f"{int(row['pixel_id'])}\t{{{','.join(str(v) for v in row['radiance'])}}}\n"
            for _, row in df.iterrows()
        ]
        buf = io.StringIO("".join(rows))
        with conn.cursor() as cur:
            cur.copy_expert("""
                COPY vswir_plants.extracted_spectra (pixel_id, radiance)
                FROM STDIN WITH (FORMAT TEXT)
            """, buf)

        offset += CHUNK_SIZE


def _cleanup_staging(conn, batch_id: str):
    with conn.cursor() as cur:
        for table in STAGING_TABLES:
            cur.execute(
                f"DELETE FROM vswir_plants_staging.{table} WHERE batch_id = %s",
                (batch_id,)
            )
            logger.info("Deleted staging.%s for batch_id=%s", table, batch_id)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _engine_from_conn(conn):
    return create_engine(
        "postgresql+psycopg2://",
        creator=lambda: conn,
        poolclass=StaticPool,
    )
