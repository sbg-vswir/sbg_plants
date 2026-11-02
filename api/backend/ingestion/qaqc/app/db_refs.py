"""
Production DB reference set loaders for the QAQC lambda.

Uses pandas/geopandas instead of raw psycopg2 cursors.
Requires a SQLAlchemy connection (from db.get_connection()).
"""

import logging
import pandas as pd
import geopandas as gpd

logger = logging.getLogger(__name__)


def load_all(conn) -> dict:
    """
    Load all production reference sets needed for QAQC cross-referencing.
    Returns a dict with named sets/maps.

    Every set here corresponds to the natural key of a production table that
    gets written during ingestion. Each check file uses check_not_in_db() to
    ensure no bundle row would violate a PK or unique constraint in production.
    """
    logger.info("Loading production reference sets for QAQC")
    return {
        # campaign
        "campaign_names":             fetch_campaign_names(conn),
        "campaign_sensor_set":        fetch_campaign_sensor_set(conn),
        # granule
        "granule_ids":                fetch_granule_ids(conn),
        "granule_gsd_map":            fetch_granule_gsd_map(conn),
        # plots
        "plot_set":                   fetch_plot_set(conn),
        "plot_intersect_set":         fetch_plot_intersect_set(conn),
        "plot_shape_map":             fetch_plot_shape_map(conn),
        # traits
        "insitu_plot_event_set":      fetch_insitu_plot_event_set(conn),
        "sample_set":                 fetch_sample_set(conn),
        "leaf_trait_set":             fetch_leaf_trait_set(conn),
        # spectra
        "pixel_set":                  fetch_pixel_set(conn),
        # wavelengths (band counts — used for spectra band count check)
        "wavelength_band_counts":     fetch_wavelength_band_counts(conn),
    }


# ── campaign ───────────────────────────────────────────────────────────────────

def fetch_campaign_names(conn) -> set:
    """Set of campaign_names already in production campaign table."""
    df = pd.read_sql("SELECT campaign_name FROM vswir_plants.campaign", conn)
    return set(df["campaign_name"])


def fetch_campaign_sensor_set(conn) -> set:
    """Set of (campaign_name, sensor_name) tuples in production sensor_campaign."""
    df = pd.read_sql(
        "SELECT campaign_name, sensor_name FROM vswir_plants.sensor_campaign",
        conn,
    )
    return set(zip(df["campaign_name"], df["sensor_name"]))


# ── granule ────────────────────────────────────────────────────────────────────

def fetch_granule_ids(conn) -> set:
    """Set of granule_ids already in production."""
    df = pd.read_sql("SELECT granule_id FROM vswir_plants.granule", conn)
    return set(df["granule_id"])


def fetch_granule_gsd_map(conn) -> dict:
    """Map of granule_id → gsd (metres) from production."""
    df = pd.read_sql("SELECT granule_id, gsd FROM vswir_plants.granule", conn)
    return dict(zip(df["granule_id"], df["gsd"].astype(float)))


# ── plots ──────────────────────────────────────────────────────────────────────

def fetch_plot_set(conn) -> set:
    """Set of (campaign_name, plot_name) tuples in production plot table."""
    df = pd.read_sql(
        "SELECT campaign_name, plot_name FROM vswir_plants.plot",
        conn,
    )
    return set(zip(df["campaign_name"], df["plot_name"]))


def fetch_plot_intersect_set(conn) -> set:
    """Set of (campaign_name, plot_name, granule_id) in production plot_raster_intersect."""
    df = pd.read_sql(
        """
        SELECT pl.campaign_name, pl.plot_name, pri.granule_id
        FROM vswir_plants.plot_raster_intersect pri
        JOIN vswir_plants.plot pl ON pl.plot_id = pri.plot_id
        """,
        conn,
    )
    return set(zip(df["campaign_name"], df["plot_name"], df["granule_id"]))


def fetch_plot_shape_map(conn) -> dict:
    """
    Map of (campaign_name, plot_name, granule_id) → Shapely geometry.
    geopandas.read_postgis handles PostGIS geometry parsing automatically.
    """
    gdf = gpd.read_postgis(
        """
        SELECT pl.campaign_name, pl.plot_name, pri.granule_id,
               ps.geom
        FROM vswir_plants.plot_raster_intersect pri
        JOIN vswir_plants.plot pl ON pl.plot_id = pri.plot_id
        JOIN vswir_plants.plot_shape ps ON ps.plot_shape_id = pri.plot_shape_id
        """,
        conn,
        geom_col="geom",
    )
    return {
        (row["campaign_name"], row["plot_name"], row["granule_id"]): row["geom"]
        for _, row in gdf.iterrows()
    }


# ── traits ─────────────────────────────────────────────────────────────────────

def fetch_insitu_plot_event_set(conn) -> set:
    """
    Set of (campaign_name, plot_name, collection_date) in production.
    PK on insitu_plot_event is (plot_id, collection_date) — joined to plot
    to get the natural key.
    """
    df = pd.read_sql(
        """
        SELECT pl.campaign_name, pl.plot_name,
               ipe.collection_date::text AS collection_date
        FROM vswir_plants.insitu_plot_event ipe
        JOIN vswir_plants.plot pl ON pl.plot_id = ipe.plot_id
        """,
        conn,
    )
    return set(zip(df["campaign_name"], df["plot_name"], df["collection_date"]))


def fetch_sample_set(conn) -> set:
    """
    Set of (campaign_name, plot_name, collection_date, sample_name) in production.
    PK on sample is (plot_id, collection_date, sample_name).
    """
    df = pd.read_sql(
        """
        SELECT pl.campaign_name, pl.plot_name,
               s.collection_date::text AS collection_date,
               s.sample_name
        FROM vswir_plants.sample s
        JOIN vswir_plants.plot pl ON pl.plot_id = s.plot_id
        """,
        conn,
    )
    return set(zip(
        df["campaign_name"], df["plot_name"],
        df["collection_date"], df["sample_name"],
    ))


def fetch_leaf_trait_set(conn) -> set:
    """
    Set of (campaign_name, plot_name, collection_date, sample_name, trait) in production.
    PK on leaf_traits is (plot_id, collection_date, sample_name, trait).
    """
    df = pd.read_sql(
        """
        SELECT pl.campaign_name, pl.plot_name,
               lt.collection_date::text AS collection_date,
               lt.sample_name, lt.trait::text AS trait
        FROM vswir_plants.leaf_traits lt
        JOIN vswir_plants.plot pl ON pl.plot_id = lt.plot_id
        """,
        conn,
    )
    return set(zip(
        df["campaign_name"], df["plot_name"],
        df["collection_date"], df["sample_name"], df["trait"],
    ))


# ── spectra ────────────────────────────────────────────────────────────────────

def fetch_pixel_set(conn) -> set:
    """
    Set of (campaign_name, plot_name, granule_id, glt_row, glt_column) in production.
    Unique index on pixel is (plot_id, granule_id, glt_row, glt_column) — joined
    to plot to get the natural key.
    """
    df = pd.read_sql(
        """
        SELECT pl.campaign_name, pl.plot_name,
               px.granule_id, px.glt_row, px.glt_column
        FROM vswir_plants.pixel px
        JOIN vswir_plants.plot pl ON pl.plot_id = px.plot_id
        """,
        conn,
    )
    return set(zip(
        df["campaign_name"], df["plot_name"],
        df["granule_id"], df["glt_row"], df["glt_column"],
    ))


# ── wavelengths ────────────────────────────────────────────────────────────────

def fetch_wavelength_band_counts(conn) -> dict:
    """Map of (campaign_name, sensor_name) → band count in production."""
    df = pd.read_sql(
        """
        SELECT campaign_name, sensor_name,
               array_length(wavelength_center, 1) AS band_count
        FROM vswir_plants.sensor_campaign
        """,
        conn,
    )
    return {
        (row["campaign_name"], row["sensor_name"]): row["band_count"]
        for _, row in df.iterrows()
    }
