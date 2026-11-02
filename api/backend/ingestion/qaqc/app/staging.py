"""
Staging inserts for the QAQC lambda.

Loads validated bundle data into vswir_plants_staging in dependency order.
Uses pandas/geopandas for bulk inserts and copy_expert for large tables.
"""

import io
import json
import logging
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
import psycopg2.extras
from contextlib import contextmanager

from app.checks.universal import row_key
from app.db_refs import PLOT_KEY

logger     = logging.getLogger(__name__)
CHUNK_SIZE = 5000

# ── Type coercion ─────────────────────────────────────────────────────────────
#
# Every bundle CSV is parsed with dtype=str (s3_files.py) — every column,
# including numeric and boolean ones, arrives as a plain string. That string
# doesn't always match what Postgres's own input parsers accept:
#   - integers: "23730.0" (a spreadsheet-exported whole number) fails
#     int()/COPY's int4in outright — neither accepts a decimal point.
#   - booleans: "0.0"/"1.0" fails Postgres's boolin — it only recognizes a
#     fixed set of tokens (true/false/t/f/yes/no/y/n/on/off/1/0), none of
#     which have a decimal point either.
# This surfaced one column at a time (glt_row, glt_column, raster_epsg,
# sample_fc_percent, now shade_mask) because each was only ever reached once
# earlier bugs blocking the pipeline got fixed — not because the problem was
# actually specific to any one of them. These two helpers are the fix,
# applied to every integer/boolean column loaded from raw bundle data
# (anything sourced from an internal id-lookup dict, e.g. plot_id, is
# already a genuine Python int from a cursor result and doesn't need this).

def _coerce_int(series: pd.Series) -> pd.Series:
    """
    Parse a string-typed numeric column (possibly formatted like "23730.0")
    into real numeric values, coercing anything unparseable (including a
    blank "") to NaN. Returns floats — caller should dropna() then
    .astype(int) once any required-but-missing rows have been handled.
    """
    return pd.to_numeric(series, errors="coerce")


_BOOL_TRUTHY = {"true", "t", "yes", "y", "on", "1"}

def _coerce_bool(series: pd.Series) -> pd.Series:
    def to_bool(val):
        if pd.isna(val):
            return None

        s = str(val).strip().lower()
        if not s:
            return None

        try:
            return float(s) != 0
        except ValueError:
            return s in _BOOL_TRUTHY

    return series.apply(to_bool)


# Reverse dependency order for safe deletion — same list used by
# promotion/app/promote.py::_cleanup_staging and rejection/app/main.py
# (kept in sync manually; these are three separate Lambda deployments with
# no shared package today).
STAGING_TABLES = [
    "extracted_spectra", "pixel", "leaf_traits", "sample",
    "insitu_plot_event", "plot_raster_intersect", "plot",
    "plot_shape", "granule", "sensor_campaign", "doi", "campaign",
]


@contextmanager
def staging_transaction(conn):
    """
    Commit on clean exit, rollback on any exception.

    Explicitly opens the transaction with conn.begin() *before* yielding —
    this is not optional. pandas' to_sql()/to_postgis() check
    conn.in_transaction() themselves: if nothing is open yet, they open
    their own transaction and commit+close it as soon as that one call
    returns, regardless of this context manager still being "open" around
    it. That reproduced the exact non-atomic-partial-commit bug this
    function exists to prevent, just one level removed (pandas doing its
    own per-call commit instead of a separate pooled connection doing it).
    Starting the transaction here first means conn.in_transaction() is
    already True by the time the first to_sql() call happens, so pandas
    correctly defers to this transaction instead of managing its own.
    """
    trans = conn.begin()
    try:
        yield conn
        trans.commit()
    except Exception:
        trans.rollback()
        raise


def purge_staging(conn, batch_id: str) -> None:
    """
    Delete any existing staging rows for batch_id, in reverse dependency
    order, and commit immediately (independent of load_all's own
    transaction). Defensive belt-and-suspenders: with load_all now sharing a
    single connection/transaction (see its docstring), a failed load_all
    should always roll back cleanly on its own — but this guarantees a QAQC
    run (fresh or rechecked) always starts from a clean slate for this
    batch_id regardless of how a partial state might have been left behind
    (e.g. a Lambda timeout mid-transaction, or a run from before that fix
    shipped). Committing here — rather than leaving it pending inside the
    same transaction as the reload — matters: if the reload then fails, we
    still want the purge to have stuck, not roll back to the stale state it
    was meant to clear. Safe to call even if nothing is staged yet — every
    DELETE is a no-op then.
    """
    raw = conn.connection
    with raw.cursor() as cur:
        for table in STAGING_TABLES:
            cur.execute(
                f"DELETE FROM vswir_plants_staging.{table} WHERE batch_id = %s",
                (batch_id,),
            )
    conn.commit()
    logger.info("Purged any existing staging rows for batch_id=%s", batch_id)


def load_all(conn, batch_id: str, dfs: dict, existing: dict, prod_plot_ids: dict) -> dict:
    """
    Load all bundle data into staging in dependency order.
    Returns row counts per table.

    dfs:           { slot: DataFrame | None } — None for a file not in the bundle.
    existing:      { table: boolean Series } from QAQC — rows already in
                   production with identical values. They are reused, not staged.
    prod_plot_ids: { (campaign_name, plot_name): plot_id } for production plots.

    plot_id / plot_shape_id / pixel_id come from the production sequences (see
    plants_v5_staging_tables.sql), so child rows store the id the parent has
    (or will have) in production, whether the parent is new in this batch or
    already in production. A child whose parent can't be resolved raises —
    QAQC should already have caught it, so this is a bug, not a data error.

    conn is a SQLAlchemy Connection. Every loader below is passed conn itself
    (never conn.engine) so every insert shares this exact connection/transaction.

    IMPORTANT: passing conn.engine to to_sql()/to_postgis() (as this function
    used to) makes pandas/geopandas check out a *separate* connection from the
    pool and auto-commit it immediately — completely bypassing the rollback
    below and invisible to raw-cursor work on `conn.connection` until (or
    unless) that separate connection's own commit lands. That mismatch is what
    caused a previous production incident: campaign/doi rows committed and
    persisted independently while a later step in the "same" transaction
    failed and rolled back only the raw-cursor half of the work, and a
    same-batch FK check failed because the two connections couldn't see each
    other's uncommitted rows. Always pass conn (never conn.engine) here.
    """
    raw = conn.connection

    def new_rows(df, table):
        """Rows of df not already in production (None if the file wasn't provided)."""
        if df is None:
            return None
        mask = existing.get(table)
        return df if mask is None else df[~mask.reindex(df.index, fill_value=False)]

    campaign_df = dfs["campaign_metadata"]
    plots_gdf   = dfs["plot_geometry"]
    traits_df   = dfs["traits"]
    spectra_df  = dfs["spectra"]

    row_counts = {}
    with staging_transaction(conn):
        row_counts["campaign"]        = _load_campaign(conn, new_rows(campaign_df, "campaign"), batch_id)
        row_counts["doi"]             = _load_doi(raw, new_rows(dfs["doi"], "doi"), batch_id)
        row_counts["sensor_campaign"] = _load_sensor_campaign(raw, new_rows(campaign_df, "sensor_campaign"), batch_id)
        row_counts["granule"]         = _load_granule(conn, dfs["granule_metadata"], batch_id)

        plot_lookup = dict(prod_plot_ids)
        if plots_gdf is not None and not plots_gdf.empty:
            new_plot_ids = _load_plots(raw, new_rows(plots_gdf, "plot"), batch_id)
            plot_lookup.update(new_plot_ids)
            row_counts["plot"]                  = len(new_plot_ids)
            row_counts["plot_shape"]            = len(plots_gdf)
            row_counts["plot_raster_intersect"] = _load_plot_raster_intersect(conn, plots_gdf, plot_lookup, batch_id)

        if traits_df is not None and not traits_df.empty:
            row_counts["insitu_plot_event"] = _load_insitu_plot_event(conn, new_rows(traits_df, "insitu_plot_event"), plot_lookup, batch_id)
            row_counts["sample"]            = _load_sample(conn, new_rows(traits_df, "sample"), plot_lookup, batch_id)
            row_counts["leaf_traits"]       = _load_leaf_traits(conn, new_rows(traits_df, "leaf_traits"), plot_lookup, batch_id)

        if spectra_df is not None and not spectra_df.empty:
            pixel_id_map                    = _load_pixels(raw, spectra_df, plot_lookup, batch_id)
            row_counts["pixel"]             = len(pixel_id_map)
            row_counts["extracted_spectra"] = _load_spectra(raw, spectra_df, plot_lookup, pixel_id_map, batch_id)

    return row_counts


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load_campaign(conn, df: pd.DataFrame | None, batch_id: str) -> int:
    if df is None or df.empty:
        return 0
    out = (
        df[["campaign_name", "primary_funding_source", "data_repository", "taxa_system"]]
        .drop_duplicates("campaign_name")
        .assign(batch_id=batch_id)
        .replace("", None)
    )
    out.to_sql(
        "campaign", conn, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi",
    )
    return len(out)


def _load_doi(conn, df: pd.DataFrame | None, batch_id: str) -> int:
    """
    Insert doi.csv rows into the doi staging table, one row per csv row.
    Uses execute_values because site_ids is a VARCHAR[] array. site_ids
    arrives already normalized (sorted, ';'-joined) from checks/doi.py, and
    duplicates were already rejected there, so nothing is deduped here.
    """
    if df is None or df.empty:
        return 0
    cols = ["campaign_name", "doi", "citation_text", "role",
            "sensor_name", "plot_method", "trait", "trait_method"]

    def _val(row, col):
        val = row.get(col, "")
        return None if pd.isna(val) or str(val).strip() == "" else str(val).strip()

    rows = [
        tuple(_val(row, c) for c in cols)
        + ((_val(row, "site_ids").split(";") if _val(row, "site_ids") else None), batch_id)
        for _, row in df.iterrows()
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO vswir_plants_staging.doi
                (campaign_name, doi, citation_text, role, sensor_name, plot_method,
                 trait, trait_method, site_ids, batch_id)
            VALUES %s
        """, rows)
    return len(rows)


def _load_sensor_campaign(conn, df: pd.DataFrame | None, batch_id: str) -> int:
    """Uses execute_values because wavelength_center and fwhm are FLOAT4[] arrays."""
    if df is None or df.empty:
        return 0
    out = (
        df[["campaign_name", "sensor_name", "sensor_date", "elevation_source", "wavelength_center", "fwhm"]]
        .drop_duplicates(["campaign_name", "sensor_name", "sensor_date"])
    )
    rows = [
        (
            row["campaign_name"],
            row["sensor_name"],
            row["sensor_date"],
            row["elevation_source"],
            row["wavelength_center"],  # already a list from main.py
            row["fwhm"],
            batch_id,
        )
        for _, row in out.iterrows()
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO vswir_plants_staging.sensor_campaign
                (campaign_name, sensor_name, sensor_date, elevation_source, wavelength_center, fwhm, batch_id)
            VALUES %s
        """, rows)
    return len(rows)


def _load_granule(conn, df: pd.DataFrame | None, batch_id: str) -> int:
    # Explicit column allowlist matching the granule table exactly — this
    # used to insert the whole parsed df as-is, which only worked by
    # coincidence (df happened to carry no extra columns). Same class of bug
    # as the plot_shape "_key" column: to_sql() with no column list sends
    # every DataFrame column, and any stray one not present on the table
    # fails with "column ... does not exist". Explicit is safe regardless of
    # what upstream parsing/QAQC checks add to df in the future.
    if df is None or df.empty:
        return 0
    granule_cols = [
        "granule_id", "campaign_name", "sensor_name", "sensor_date", "acquisition_start_time",
        "acquisition_date", "granule_rad_url", "granule_refl_url", "flightline_id",
        "cloudy_conditions", "cloud_type", "gsd", "raster_epsg",
    ]
    out = (
        df[[c for c in granule_cols if c in df.columns]]
        .assign(batch_id=batch_id)
        .replace("", None)
    )
    if "raster_epsg" in out.columns:
        out["raster_epsg"] = _coerce_int(out["raster_epsg"]).astype(int)  # INTEGER NOT NULL
    out.to_sql(
        "granule", conn, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi", chunksize=CHUNK_SIZE,
    )
    return len(out)


def _load_plots(conn, gdf: gpd.GeoDataFrame, batch_id: str) -> dict:
    """
    Insert the plots that are new in this batch (plots already in production
    were dropped by the caller). plot_id comes from the production sequence.
    Returns { (campaign_name, plot_name): plot_id }
    """
    unique = gdf.drop_duplicates(subset=["campaign_name", "plot_name"])
    if unique.empty:
        return {}
    plot_rows = list(zip(
        unique["campaign_name"],
        unique["site_id"],
        unique["plot_name"],
        unique["plot_method"].replace("", None) if "plot_method" in unique.columns else [None] * len(unique),
        [batch_id] * len(unique),
    ))

    with conn.cursor() as cur:
        results = psycopg2.extras.execute_values(cur, """
            INSERT INTO vswir_plants_staging.plot
                (campaign_name, site_id, plot_name, plot_method, batch_id)
            VALUES %s
            RETURNING plot_id, campaign_name, plot_name
        """, plot_rows, fetch=True)

    return {row_key({"campaign_name": r[1], "plot_name": r[2]}, PLOT_KEY): r[0] for r in results}


def _load_plot_raster_intersect(conn, gdf: gpd.GeoDataFrame, plot_lookup: dict, batch_id: str) -> int:
    """
    One plot shape and one intersect per plots.geojson feature (every
    intersect is new — QAQC rejects one that's already in production). The
    shapes are inserted first; plot_shape_id comes from the production
    sequence, in insertion order.
    """
    shapes = gdf[[gdf.geometry.name]].copy()
    shapes["batch_id"] = batch_id
    # The staging plot_shape table's geometry column is named "geom", not
    # "geometry" (GeoPandas' default active-geometry column name from the
    # parsed plots.geojson). to_postgis() writes to a column matching
    # whatever the GeoDataFrame's geometry column is currently named, so
    # without this rename it silently targets a nonexistent "geometry"
    # column — which only surfaces once geoalchemy2 is present to actually
    # compile the insert, as a Find_SRID() failure rather than a clearer
    # "column does not exist" error.
    shapes = shapes.rename_geometry("geom")
    shapes.to_postgis(
        "plot_shape", conn, schema="vswir_plants_staging",
        if_exists="append", index=False,
    )
    with conn.connection.cursor() as cur:
        cur.execute("""
            SELECT plot_shape_id FROM vswir_plants_staging.plot_shape
            WHERE batch_id = %s ORDER BY plot_shape_id
        """, (batch_id,))
        shape_ids = [r[0] for r in cur.fetchall()]
    if len(shape_ids) != len(gdf):
        raise RuntimeError(f"expected {len(gdf)} staged plot shapes, found {len(shape_ids)}")

    out = pd.DataFrame({
        "plot_id":       _plot_ids(gdf, plot_lookup, "plots.geojson").values,
        "granule_id":    gdf["granule_id"].values,
        "plot_shape_id": shape_ids,
        "extraction_method":        gdf["extraction_method"].values,
        "delineation_method":       gdf["delineation_method"].values,
        "shape_aligned_to_granule": _coerce_bool(gdf["shape_aligned_to_granule"]).values,
        "polygon_confidence":       gdf["polygon_confidence"].values,
        "batch_id":                 batch_id,
    })
    out.to_sql(
        "plot_raster_intersect", conn, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi",
    )
    return len(out)


def _load_insitu_plot_event(conn, df: pd.DataFrame, plot_lookup: dict, batch_id: str) -> int:
    out = (
        df[["campaign_name", "plot_name", "collection_date",
            "plot_veg_type", "subplot_cover_method", "floristic_survey"]]
        .drop_duplicates(["campaign_name", "plot_name", "collection_date"])
    )
    if out.empty:
        return 0
    out = (
        out.assign(
            plot_id=lambda d: _plot_ids(d, plot_lookup, "traits.csv"),
            floristic_survey=lambda d: _coerce_bool(d["floristic_survey"]),
            batch_id=batch_id,
        )
        .drop(columns=["campaign_name", "plot_name"])
    )
    out.to_sql(
        "insitu_plot_event", conn, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi",
    )
    return len(out)


def _load_sample(conn, df: pd.DataFrame, plot_lookup: dict, batch_id: str) -> int:
    sample_cols = [
        "campaign_name", "plot_name", "collection_date", "sample_name",
        "taxa", "veg_or_cover_type", "phenophase", "sample_fc_class",
        "sample_fc_percent", "plant_status", "canopy_position",
    ]
    out = (
        df[sample_cols]
        .drop_duplicates(["campaign_name", "plot_name", "collection_date", "sample_name"])
    )
    if out.empty:
        return 0
    out = (
        out.assign(
            plot_id=lambda d: _plot_ids(d, plot_lookup, "traits.csv"),
            sample_fc_percent=lambda d: _coerce_int(d["sample_fc_percent"]).astype(int),  # INTEGER NOT NULL
            batch_id=batch_id,
        )
        .drop(columns=["campaign_name", "plot_name"])
    )
    out.to_sql(
        "sample", conn, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi",
    )
    return len(out)


def _load_leaf_traits(conn, df: pd.DataFrame, plot_lookup: dict, batch_id: str) -> int:
    """
    Only rows with actual trait data get a leaf_traits record. Sample-only
    rows (trait/method/handling/units all blank) are skipped here — they
    still contribute to the `sample` table via _load_sample, but trait,
    value, method, handling, and units are all NOT NULL on leaf_traits, so
    inserting a blank row would fail the insert (and roll back the whole
    staging transaction). _check_trait_fields in traits.py already enforces
    that trait fields are either all populated or all blank before QAQC
    ever reaches this point, so filtering on "trait" alone is sufficient.
    """
    trait_cols = [
        "campaign_name", "plot_name", "collection_date", "sample_name",
        "trait", "value", "method", "handling", "units", "error", "error_type",
    ]
    # error / error_type are nullable and may be omitted from traits.csv
    available_trait_cols = [c for c in trait_cols if c in df.columns]
    has_trait = df["trait"].notna() & (df["trait"].astype(str).str.strip() != "")
    out = df.loc[has_trait, available_trait_cols]
    if out.empty:
        return 0
    out = (
        out.assign(plot_id=lambda d: _plot_ids(d, plot_lookup, "traits.csv"), batch_id=batch_id)
        .drop(columns=["campaign_name", "plot_name"])
        .replace("", None)
    )
    out.to_sql(
        "leaf_traits", conn, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi", chunksize=CHUNK_SIZE,
    )
    return len(out)


def _load_pixels(conn, df: pd.DataFrame, plot_lookup: dict, batch_id: str) -> dict:
    """
    Bulk insert pixels using copy_expert for speed. pixel_id comes from the
    production sequence.
    Returns { (plot_id, granule_id, glt_row, glt_column): pixel_id }
    """
    pixel_cols = [
        "campaign_name", "plot_name", "granule_id", "glt_row", "glt_column",
        "shade_mask", "path_length", "to_sensor_azimuth", "to_sensor_zenith",
        "to_sun_azimuth", "to_sun_zenith", "solar_phase", "slope", "aspect",
        "utc_time", "cosine_i", "lon", "lat", "elevation",
    ]
    out = (
        df[[c for c in pixel_cols if c in df.columns]]
        .assign(
            plot_id=lambda d: _plot_ids(d, plot_lookup, "spectra.csv"),
            glt_row=lambda d: _coerce_int(d["glt_row"]).astype(int),        # INTEGER NOT NULL, QAQC checked castable
            glt_column=lambda d: _coerce_int(d["glt_column"]).astype(int),  # INTEGER NOT NULL, QAQC checked castable
            shade_mask=lambda d: _coerce_bool(d["shade_mask"]) if "shade_mask" in d.columns else None,
            batch_id=batch_id,
        )
    )

    db_cols = [
        "plot_id", "granule_id", "glt_row", "glt_column", "shade_mask",
        "path_length", "to_sensor_azimuth", "to_sensor_zenith",
        "to_sun_azimuth", "to_sun_zenith", "solar_phase", "slope", "aspect",
        "utc_time", "cosine_i", "lon", "lat", "elevation", "batch_id",
    ]
    insert_df = out[[c for c in db_cols if c in out.columns]]

    buf = io.StringIO()
    insert_df.to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)

    with conn.cursor() as cur:
        cur.copy_expert(f"""
            COPY vswir_plants_staging.pixel ({','.join(insert_df.columns)})
            FROM STDIN WITH (FORMAT CSV, NULL '\\N')
        """, buf)

        # Fetch back the generated pixel_ids with their keys
        cur.execute("""
            SELECT pixel_id, plot_id, granule_id, glt_row, glt_column
            FROM vswir_plants_staging.pixel
            WHERE batch_id = %s
        """, (batch_id,))
        rows = cur.fetchall()

    return {(plot_id, granule_id, glt_row, glt_col): pixel_id
            for pixel_id, plot_id, granule_id, glt_row, glt_col in rows}


def _load_spectra(conn, df: pd.DataFrame, plot_lookup: dict, pixel_id_map: dict, batch_id: str) -> int:
    """
    Bulk insert extracted_spectra using copy_expert.
    Assembles the radiance array per pixel and streams to Postgres.
    """
    band_cols = sorted([c for c in df.columns if _is_band_col(c)], key=int)
    plot_ids  = _plot_ids(df, plot_lookup, "spectra.csv")
    glt_rows  = _coerce_int(df["glt_row"]).astype(int)
    glt_cols  = _coerce_int(df["glt_column"]).astype(int)

    rows = []
    for idx, row in df.iterrows():
        key = (plot_ids[idx], row["granule_id"], glt_rows[idx], glt_cols[idx])
        pixel_id = pixel_id_map.get(key)
        if pixel_id is None:
            raise RuntimeError(f"spectra.csv row {idx + 2}: no staged pixel for {key}")
        radiance = "{" + ",".join(str(row[c]) for c in band_cols) + "}"
        rows.append(f"{pixel_id}\t{radiance}\t{batch_id}\n")

    if not rows:
        return 0

    buf = io.StringIO("".join(rows))
    with conn.cursor() as cur:
        cur.copy_expert("""
            COPY vswir_plants_staging.extracted_spectra (pixel_id, radiance, batch_id)
            FROM STDIN WITH (FORMAT TEXT)
        """, buf)

    return len(rows)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _plot_ids(df: pd.DataFrame, plot_lookup: dict, file_name: str) -> pd.Series:
    """
    plot_id for each row's (campaign_name, plot_name), from this batch's new
    plots or production. Raises instead of dropping rows that don't resolve.
    """
    ids = pd.Series(
        [plot_lookup.get(row_key(r, PLOT_KEY)) for _, r in df[["campaign_name", "plot_name"]].iterrows()],
        index=df.index, dtype=object,
    )
    missing = df.loc[ids.isna(), ["campaign_name", "plot_name"]].drop_duplicates()
    if not missing.empty:
        sample = ", ".join(f"({c}, {p})" for c, p in missing.head(5).itertuples(index=False))
        raise RuntimeError(
            f"{file_name}: {len(missing)} plot(s) not found in this batch or production: {sample}"
        )
    return ids.astype(int)


def _is_band_col(col: str) -> bool:
    try:
        int(col)
        return True
    except (ValueError, TypeError):
        return False
