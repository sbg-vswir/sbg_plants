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
from sqlalchemy import text
import psycopg2.extras

logger     = logging.getLogger(__name__)
CHUNK_SIZE = 5000


def load_all(conn, batch_id: str, dfs: dict, geojson: dict) -> dict:
    """
    Load all bundle data into staging in dependency order.
    Returns row counts per table.
    conn is a SQLAlchemy connection; engine is derived from it.
    """
    engine = conn.engine
    # Raw psycopg2 connection needed for copy_expert and execute_values
    raw = conn.connection

    row_counts = {}
    row_counts["campaign"]              = _load_campaign(engine, dfs["campaign_metadata"], batch_id)
    row_counts["sensor_campaign"]       = _load_sensor_campaign(raw, dfs["campaign_metadata"], batch_id)
    row_counts["granule"]               = _load_granule(engine, dfs["granule_metadata"], batch_id)
    shape_id_map                        = _load_plot_shapes(raw, engine, geojson, batch_id)
    row_counts["plot_shape"]            = len(shape_id_map)
    plot_id_map                         = _load_plots(raw, geojson, batch_id)
    row_counts["plot"]                  = len(plot_id_map)
    row_counts["plot_raster_intersect"] = _load_plot_raster_intersect(engine, geojson, plot_id_map, shape_id_map, batch_id)
    row_counts["insitu_plot_event"]     = _load_insitu_plot_event(engine, dfs["traits"], plot_id_map, batch_id)
    row_counts["sample"]                = _load_sample(engine, dfs["traits"], plot_id_map, batch_id)
    row_counts["leaf_traits"]           = _load_leaf_traits(engine, dfs["traits"], plot_id_map, batch_id)
    pixel_id_map                        = _load_pixels(raw, dfs["spectra"], plot_id_map, batch_id)
    row_counts["pixel"]                 = len(pixel_id_map)
    row_counts["extracted_spectra"]     = _load_spectra(raw, dfs["spectra"], pixel_id_map, batch_id)
    conn.commit()

    return row_counts


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load_campaign(engine, df: pd.DataFrame, batch_id: str) -> int:
    out = (
        df[["campaign_name", "primary_funding_source", "data_repository", "doi", "taxa_system"]]
        .drop_duplicates("campaign_name")
        .assign(batch_id=batch_id)
        .replace("", None)
    )
    out.to_sql(
        "campaign", engine, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi",
    )
    return len(out)


def _load_sensor_campaign(conn, df: pd.DataFrame, batch_id: str) -> int:
    """Uses execute_values because wavelength_center and fwhm are FLOAT4[] arrays."""
    out = (
        df[["campaign_name", "sensor_name", "elevation_source", "wavelength_center", "fwhm"]]
        .drop_duplicates(["campaign_name", "sensor_name"])
    )
    rows = [
        (
            row["campaign_name"],
            row["sensor_name"],
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
                (campaign_name, sensor_name, elevation_source, wavelength_center, fwhm, batch_id)
            VALUES %s
            ON CONFLICT DO NOTHING
        """, rows)
    return len(rows)


def _load_granule(engine, df: pd.DataFrame, batch_id: str) -> int:
    out = df.assign(batch_id=batch_id).replace("", None)
    out.to_sql(
        "granule", engine, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi", chunksize=CHUNK_SIZE,
    )
    return len(out)


def _load_plot_shapes(conn, engine, geojson: dict, batch_id: str) -> dict:
    """
    Insert plot shapes using GeoPandas to_postgis.
    Returns { (campaign_name, plot_name, granule_id): staging_plot_shape_id }
    """
    features = geojson["features"]
    geoms    = [shape(f["geometry"]) for f in features]
    keys     = [
        (f["properties"]["campaign_name"], f["properties"]["plot_name"], f["properties"]["granule_id"])
        for f in features
    ]

    gdf = gpd.GeoDataFrame(
        {"batch_id": [batch_id] * len(features), "_key": keys},
        geometry=geoms,
        crs="EPSG:4326",
    )
    gdf.to_postgis(
        "plot_shape", engine, schema="vswir_plants_staging",
        if_exists="append", index=False,
    )

    # Fetch back the generated plot_shape_ids in insertion order
    with conn.cursor() as cur:
        cur.execute("""
            SELECT plot_shape_id FROM vswir_plants_staging.plot_shape
            WHERE batch_id = %s ORDER BY plot_shape_id
        """, (batch_id,))
        ids = [r[0] for r in cur.fetchall()]

    return dict(zip(keys, ids))


def _load_plots(conn, geojson: dict, batch_id: str) -> dict:
    """
    Insert unique plots using execute_values with RETURNING to capture plot_ids.
    Returns { (campaign_name, plot_name): staging_plot_id }
    """
    seen      = {}
    plot_rows = []
    for f in geojson["features"]:
        p   = f["properties"]
        key = (p["campaign_name"], p["plot_name"])
        if key not in seen:
            seen[key] = True
            plot_rows.append((p["campaign_name"], p["site_id"], p["plot_name"], p.get("plot_method"), batch_id))

    with conn.cursor() as cur:
        results = psycopg2.extras.execute_values(cur, """
            INSERT INTO vswir_plants_staging.plot
                (campaign_name, site_id, plot_name, plot_method, batch_id)
            VALUES %s
            ON CONFLICT DO NOTHING
            RETURNING plot_id, campaign_name, plot_name
        """, plot_rows, fetch=True)

    return {(r[1], r[2]): r[0] for r in results}


def _load_plot_raster_intersect(engine, geojson: dict, plot_id_map: dict, shape_id_map: dict, batch_id: str) -> int:
    rows = []
    for f in geojson["features"]:
        p         = f["properties"]
        plot_key  = (p["campaign_name"], p["plot_name"])
        shape_key = (p["campaign_name"], p["plot_name"], p["granule_id"])
        plot_id   = plot_id_map.get(plot_key)
        shape_id  = shape_id_map.get(shape_key)
        if not plot_id or not shape_id:
            continue
        rows.append({
            "plot_id":                  plot_id,
            "granule_id":               p["granule_id"],
            "plot_shape_id":            shape_id,
            "extraction_method":        p["extraction_method"],
            "delineation_method":       p["delineation_method"],
            "shape_aligned_to_granule": str(p["shape_aligned_to_granule"]).lower() in ("true", "1", "yes"),
            "batch_id":                 batch_id,
        })
    out = pd.DataFrame(rows)
    out.to_sql(
        "plot_raster_intersect", engine, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi",
    )
    return len(out)


def _load_insitu_plot_event(engine, df: pd.DataFrame, plot_id_map: dict, batch_id: str) -> int:
    out = (
        df[["campaign_name", "plot_name", "collection_date",
            "plot_veg_type", "subplot_cover_method", "floristic_survey"]]
        .drop_duplicates(["campaign_name", "plot_name", "collection_date"])
        .assign(plot_id=lambda d: d.apply(lambda r: plot_id_map.get((r["campaign_name"], r["plot_name"])), axis=1))
        .dropna(subset=["plot_id"])
        .assign(plot_id=lambda d: d["plot_id"].astype(int), batch_id=batch_id)
        .drop(columns=["campaign_name", "plot_name"])
    )
    out.to_sql(
        "insitu_plot_event", engine, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi",
    )
    return len(out)


def _load_sample(engine, df: pd.DataFrame, plot_id_map: dict, batch_id: str) -> int:
    sample_cols = [
        "campaign_name", "plot_name", "collection_date", "sample_name",
        "taxa", "veg_or_cover_type", "phenophase", "sample_fc_class",
        "sample_fc_percent", "plant_status", "canopy_position",
    ]
    out = (
        df[sample_cols]
        .drop_duplicates(["campaign_name", "plot_name", "collection_date", "sample_name"])
        .assign(plot_id=lambda d: d.apply(lambda r: plot_id_map.get((r["campaign_name"], r["plot_name"])), axis=1))
        .dropna(subset=["plot_id"])
        .assign(plot_id=lambda d: d["plot_id"].astype(int), batch_id=batch_id)
        .drop(columns=["campaign_name", "plot_name"])
    )
    out.to_sql(
        "sample", engine, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi",
    )
    return len(out)


def _load_leaf_traits(engine, df: pd.DataFrame, plot_id_map: dict, batch_id: str) -> int:
    trait_cols = [
        "campaign_name", "plot_name", "collection_date", "sample_name",
        "trait", "value", "method", "handling", "units", "error", "error_type",
    ]
    out = (
        df[trait_cols]
        .assign(plot_id=lambda d: d.apply(lambda r: plot_id_map.get((r["campaign_name"], r["plot_name"])), axis=1))
        .dropna(subset=["plot_id"])
        .assign(plot_id=lambda d: d["plot_id"].astype(int), batch_id=batch_id)
        .drop(columns=["campaign_name", "plot_name"])
        .replace("", None)
    )
    out.to_sql(
        "leaf_traits", engine, schema="vswir_plants_staging",
        if_exists="append", index=False, method="multi", chunksize=CHUNK_SIZE,
    )
    return len(out)


def _load_pixels(conn, df: pd.DataFrame, plot_id_map: dict, batch_id: str) -> dict:
    """
    Bulk insert pixels using copy_expert for speed.
    Returns { (campaign_name, plot_name, granule_id, glt_row, glt_column): staging_pixel_id }
    """
    pixel_cols = [
        "campaign_name", "plot_name", "granule_id", "glt_row", "glt_column",
        "shade_mask", "path_length", "to_sensor_azimuth", "to_sensor_zenith",
        "to_sun_azimuth", "to_sun_zenith", "solar_phase", "slope", "aspect",
        "utc_time", "cosine_i", "raw_cosine_i", "lon", "lat", "elevation",
    ]
    out = (
        df[[c for c in pixel_cols if c in df.columns]]
        .assign(plot_id=lambda d: d.apply(lambda r: plot_id_map.get((r["campaign_name"], r["plot_name"])), axis=1))
        .dropna(subset=["plot_id"])
        .assign(plot_id=lambda d: d["plot_id"].astype(int), batch_id=batch_id)
    )

    db_cols = [
        "plot_id", "granule_id", "glt_row", "glt_column", "shade_mask",
        "path_length", "to_sensor_azimuth", "to_sensor_zenith",
        "to_sun_azimuth", "to_sun_zenith", "solar_phase", "slope", "aspect",
        "utc_time", "cosine_i", "raw_cosine_i", "lon", "lat", "elevation", "batch_id",
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

    # Build reverse map: (campaign_name, plot_name, granule_id, glt_row, glt_col) → pixel_id
    # Need plot_id → (campaign_name, plot_name) reverse map
    reverse_plot = {v: k for k, v in plot_id_map.items()}
    pixel_id_map = {}
    for pixel_id, plot_id, granule_id, glt_row, glt_col in rows:
        plot_key = reverse_plot.get(plot_id)
        if plot_key:
            pixel_id_map[(*plot_key, granule_id, glt_row, glt_col)] = pixel_id

    return pixel_id_map


def _load_spectra(conn, df: pd.DataFrame, pixel_id_map: dict, batch_id: str) -> int:
    """
    Bulk insert extracted_spectra using copy_expert.
    Assembles the radiance array per pixel and streams to Postgres.
    """
    band_cols = sorted([c for c in df.columns if _is_band_col(c)], key=int)

    rows = []
    for _, row in df.iterrows():
        key = (row["campaign_name"], row["plot_name"], row["granule_id"],
               int(row["glt_row"]), int(row["glt_column"]))
        pixel_id = pixel_id_map.get(key)
        if not pixel_id:
            continue
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

def _is_band_col(col: str) -> bool:
    try:
        int(col)
        return True
    except (ValueError, TypeError):
        return False
