"""
Production DB reference set loaders for the QAQC lambda.

Uses pandas/geopandas instead of raw psycopg2 cursors.
Requires a SQLAlchemy connection (from db.get_connection()).

Two kinds of reference:
  - key sets / maps — for foreign-key checks (does the parent exist in
    bundle or production?) and "must be new" checks (granule, intersect, pixel).
  - *_rows dicts — { normalized key tuple: { column: value } } for the
    reuse-if-identical rule (checks/universal.py::check_existing_identical).
    Keys are built with the same normalize() the checks use on bundle rows.
"""

import logging
import pandas as pd
import geopandas as gpd

from app.checks.universal import normalize, row_key

logger = logging.getLogger(__name__)

# Natural keys (column → normalize type) shared with the check modules
CAMPAIGN_KEY        = {"campaign_name": "str"}
SENSOR_CAMPAIGN_KEY = {"campaign_name": "str", "sensor_name": "str", "sensor_date": "date"}
PLOT_KEY            = {"campaign_name": "str", "plot_name": "str"}
PLOT_EVENT_KEY      = {**PLOT_KEY, "collection_date": "date"}
SAMPLE_KEY          = {**PLOT_EVENT_KEY, "sample_name": "str"}
LEAF_TRAIT_KEY      = {**SAMPLE_KEY, "trait": "str", "method": "str", "handling": "str", "units": "str"}
DOI_KEY             = {
    "campaign_name": "str", "doi": "lower", "role": "str", "sensor_name": "str",
    "plot_method": "str", "trait": "str", "trait_method": "str", "site_ids": "strlist",
}
DOI_REQUIRED        = ["campaign_name", "doi", "role"]  # the rest are optional scopes


def load_all(conn) -> dict:
    """
    Load all production reference sets needed for QAQC cross-referencing.
    Returns a dict with named sets/maps.
    """
    logger.info("Loading production reference sets for QAQC")
    refs = {
        # campaign
        "campaign_rows":              fetch_campaign_rows(conn),
        "sensor_campaign_rows":       fetch_sensor_campaign_rows(conn),
        # granule
        "granule_ids":                fetch_granule_ids(conn),
        "granule_gsd_map":            fetch_granule_gsd_map(conn),
        "granule_sensor_map":         fetch_granule_sensor_map(conn),
        # plots
        "plot_rows":                  fetch_plot_rows(conn),
        "plot_intersect_set":         fetch_plot_intersect_set(conn),
        "plot_shape_map":             fetch_plot_shape_map(conn),
        # traits
        "insitu_plot_event_rows":     fetch_insitu_plot_event_rows(conn),
        "sample_rows":                fetch_sample_rows(conn),
        "leaf_trait_rows":            fetch_leaf_trait_rows(conn),
        # spectra
        "pixel_set":                  fetch_pixel_set(conn),
        # doi
        "doi_rows":                   fetch_doi_rows(conn),
    }
    # key sets derived from the row dicts, for foreign-key checks
    refs["campaign_names"]         = {k[0] for k in refs["campaign_rows"]}
    refs["campaign_sensor_set"]    = set(refs["sensor_campaign_rows"])
    refs["plot_set"]               = set(refs["plot_rows"])
    refs["wavelength_band_counts"] = {
        k: len(v["wavelength_center"]) for k, v in refs["sensor_campaign_rows"].items()
    }
    return refs


def _rows(df: pd.DataFrame, key_cols: dict, required: list | None = None) -> dict:
    """{ normalized key tuple: { every other column: value } } for a query result."""
    value_cols = [c for c in df.columns if c not in key_cols]
    return {
        row_key(row, key_cols, required): {c: row[c] for c in value_cols}
        for _, row in df.iterrows()
    }


# ── campaign ───────────────────────────────────────────────────────────────────

def fetch_campaign_rows(conn) -> dict:
    df = pd.read_sql(
        """
        SELECT campaign_name::text, primary_funding_source,
               data_repository::text, taxa_system
        FROM vswir_plants.campaign
        """,
        conn,
    )
    return _rows(df, CAMPAIGN_KEY)


def fetch_sensor_campaign_rows(conn) -> dict:
    """(campaign_name, sensor_name, sensor_date) → elevation_source, wavelength_center, fwhm."""
    df = pd.read_sql(
        """
        SELECT campaign_name::text, sensor_name::text, sensor_date::text,
               elevation_source::text, wavelength_center, fwhm
        FROM vswir_plants.sensor_campaign
        """,
        conn,
    )
    return _rows(df, SENSOR_CAMPAIGN_KEY)


# ── granule ────────────────────────────────────────────────────────────────────

def fetch_granule_ids(conn) -> set:
    """Set of granule_ids already in production."""
    df = pd.read_sql("SELECT granule_id FROM vswir_plants.granule", conn)
    return set(df["granule_id"])


def fetch_granule_gsd_map(conn) -> dict:
    """Map of granule_id → gsd (metres) from production."""
    df = pd.read_sql("SELECT granule_id, gsd FROM vswir_plants.granule", conn)
    return dict(zip(df["granule_id"], df["gsd"].astype(float)))


def fetch_granule_sensor_map(conn) -> dict:
    """
    Map of granule_id → (campaign_name, sensor_name, sensor_date) from
    production. spectra.py looks up a pixel's band count through its granule.
    """
    df = pd.read_sql(
        """
        SELECT granule_id, campaign_name::text, sensor_name::text, sensor_date::text
        FROM vswir_plants.granule
        """,
        conn,
    )
    return {
        row["granule_id"]: row_key(row, SENSOR_CAMPAIGN_KEY)
        for _, row in df.iterrows()
    }


# ── plots ──────────────────────────────────────────────────────────────────────

def fetch_plot_rows(conn) -> dict:
    """(campaign_name, plot_name) → plot_id, site_id, plot_method."""
    df = pd.read_sql(
        """
        SELECT campaign_name::text, plot_name, plot_id, site_id, plot_method::text
        FROM vswir_plants.plot
        """,
        conn,
    )
    return _rows(df, PLOT_KEY)


def fetch_plot_intersect_set(conn) -> set:
    """Set of (campaign_name, plot_name, granule_id) in production plot_raster_intersect."""
    df = pd.read_sql(
        """
        SELECT pl.campaign_name::text, pl.plot_name, pri.granule_id
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
        SELECT pl.campaign_name::text, pl.plot_name, pri.granule_id,
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

def fetch_insitu_plot_event_rows(conn) -> dict:
    """(campaign_name, plot_name, collection_date) → event columns."""
    df = pd.read_sql(
        """
        SELECT pl.campaign_name::text, pl.plot_name,
               ipe.collection_date::text AS collection_date,
               ipe.plot_veg_type::text, ipe.subplot_cover_method::text,
               ipe.floristic_survey
        FROM vswir_plants.insitu_plot_event ipe
        JOIN vswir_plants.plot pl ON pl.plot_id = ipe.plot_id
        """,
        conn,
    )
    return _rows(df, PLOT_EVENT_KEY)


def fetch_sample_rows(conn) -> dict:
    """(campaign_name, plot_name, collection_date, sample_name) → sample columns."""
    df = pd.read_sql(
        """
        SELECT pl.campaign_name::text, pl.plot_name,
               s.collection_date::text AS collection_date, s.sample_name,
               s.taxa::text, s.veg_or_cover_type::text, s.phenophase::text,
               s.sample_fc_class::text, s.sample_fc_percent,
               s.plant_status::text, s.canopy_position::text
        FROM vswir_plants.sample s
        JOIN vswir_plants.plot pl ON pl.plot_id = s.plot_id
        """,
        conn,
    )
    return _rows(df, SAMPLE_KEY)


def fetch_leaf_trait_rows(conn) -> dict:
    """
    leaf_traits_unique key (campaign_name, plot_name, collection_date,
    sample_name, trait, method, handling, units) → value, error, error_type.
    """
    df = pd.read_sql(
        """
        SELECT pl.campaign_name::text, pl.plot_name,
               lt.collection_date::text AS collection_date, lt.sample_name,
               lt.trait::text, lt.method::text, lt.handling::text, lt.units::text,
               lt.value, lt.error, lt.error_type::text
        FROM vswir_plants.leaf_traits lt
        JOIN vswir_plants.plot pl ON pl.plot_id = lt.plot_id
        """,
        conn,
    )
    return _rows(df, LEAF_TRAIT_KEY)


# ── spectra ────────────────────────────────────────────────────────────────────

def fetch_pixel_set(conn) -> set:
    """
    Set of (campaign_name, plot_name, granule_id, glt_row, glt_column) in production.
    Unique index on pixel is (plot_id, granule_id, glt_row, glt_column) — joined
    to plot to get the natural key. glt_row/glt_column are ints; spectra.py
    normalizes the bundle's string values the same way.
    """
    df = pd.read_sql(
        """
        SELECT pl.campaign_name::text, pl.plot_name,
               px.granule_id, px.glt_row, px.glt_column
        FROM vswir_plants.pixel px
        JOIN vswir_plants.plot pl ON pl.plot_id = px.plot_id
        """,
        conn,
    )
    return set(zip(
        df["campaign_name"], df["plot_name"],
        df["granule_id"], df["glt_row"].astype(int), df["glt_column"].astype(int),
    ))


# ── doi ────────────────────────────────────────────────────────────────────────

def fetch_doi_rows(conn) -> dict:
    """doi_unique key (lowercased doi, sorted site_ids) → citation_text."""
    df = pd.read_sql(
        """
        SELECT campaign_name::text, doi, role::text, sensor_name::text,
               plot_method::text, trait::text, trait_method::text, site_ids,
               citation_text
        FROM vswir_plants.doi
        """,
        conn,
    )
    return _rows(df, DOI_KEY, DOI_REQUIRED)
