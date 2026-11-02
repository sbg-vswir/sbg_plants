import logging

from app.db import get_connection, load_enums
from app.s3_files import download_raw_files, parse_files, write_report
from app.dynamo import update_status
from app.db_refs import load_all as load_db_refs, SENSOR_CAMPAIGN_KEY
from app.staging import load_all as load_staging, purge_staging
from app.checks.types import CheckContext
from app.checks.runner import run_all as run_checks
from app.checks.universal import row_key
from app.checks.wavelengths import band_arrays

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    batch_id = event["batch_id"]
    logger.info("QAQC starting for batch_id=%s", batch_id)

    update_status(batch_id, "QAQC_RUNNING")

    try:
        _run_qaqc(batch_id)
    except Exception as e:
        logger.exception("Unexpected error during QAQC for batch_id=%s", batch_id)
        report = {"_error": {"row_count": 0, "errors": [
            {"file": "_error", "row": None, "column": None, "message": str(e)}
        ], "warnings": []}}
        s3_key = write_report(batch_id, "QAQC_FAIL", report)
        update_status(batch_id, "QAQC_FAIL", report, s3_key)


def _run_qaqc(batch_id: str):

    # ── 1. Download and parse the bundle files from S3 ────────────────────────
    # Every file is optional (partial bundles); a missing one parses to None.
    raw_files = download_raw_files(batch_id)

    try:
        data = parse_files(raw_files)
    except ValueError as e:
        report = {"_parse_error": {"row_count": 0, "errors": [
            {"file": "_parse_error", "row": None, "column": None, "message": str(e)}
        ], "warnings": []}}
        s3_key = write_report(batch_id, "QAQC_FAIL", report)
        update_status(batch_id, "QAQC_FAIL", report, s3_key)
        return

    # ── 2. Load DB enums and production reference sets ────────────────────────
    conn  = get_connection()
    enums = load_enums(conn)
    db    = load_db_refs(conn)

    # ── 3. Build context and run all checks ───────────────────────────────────
    # Wavelength arrays per sensor calibration (campaign, sensor, sensor_date),
    # from wavelengths.csv. Band counts are seeded into context.output before
    # the runner starts so spectra.py can look them up alongside the DB counts;
    # the arrays are attached to the sensor_campaign rows for staging below.
    wl_arrays = _wavelength_arrays(data["wavelengths"])

    context = CheckContext(
        enums=enums,
        db=db,
        data=data,
        output={
            "bundle_band_counts": {key: len(wl) for key, (wl, _) in wl_arrays.items()},
        },
    )

    report, has_errors = run_checks(context)
    report["_summary"] = _summary(data)

    # ── 4. Write full report to S3 ────────────────────────────────────────────
    final_status = "QAQC_FAIL" if has_errors else "QAQC_PASS"
    s3_key       = write_report(batch_id, final_status, report)

    if has_errors:
        logger.info("QAQC FAIL for batch_id=%s", batch_id)
        update_status(batch_id, "QAQC_FAIL", report, s3_key)
        return

    # ── 5. Load into staging ──────────────────────────────────────────────────
    logger.info("QAQC PASS — loading into staging for batch_id=%s", batch_id)

    # Purge any stale rows from a previous partial/failed attempt at this
    # batch_id before loading fresh data — see staging.py::purge_staging.
    purge_staging(conn, batch_id)

    df_campaign = data["campaign_metadata"]
    if df_campaign is not None:
        keys = [row_key(r, SENSOR_CAMPAIGN_KEY) for _, r in df_campaign.iterrows()]
        df_campaign["wavelength_center"] = [wl_arrays.get(k, ([], []))[0] for k in keys]
        df_campaign["fwhm"]              = [wl_arrays.get(k, ([], []))[1] for k in keys]

    dfs = {
        "campaign_metadata": df_campaign,
        "granule_metadata":  data["granule_metadata"],
        "traits":            data["traits"],
        "spectra":           data["spectra"],
        "doi":               data["doi"],
        "plot_geometry":     data["plots"],
    }
    # rows already in production (reused) are not staged again; their plot_ids
    # come from production
    existing      = context.output.get("existing", {})
    prod_plot_ids = {key: row["plot_id"] for key, row in db["plot_rows"].items()}

    row_counts = load_staging(conn, batch_id, dfs, existing, prod_plot_ids)
    logger.info("Staging load complete: %s", row_counts)

    for table, count in row_counts.items():
        if table in report:
            report[table]["staged_rows"] = count

    update_status(batch_id, "QAQC_PASS", report, s3_key)
    logger.info("QAQC complete for batch_id=%s", batch_id)


def _wavelength_arrays(df_wl) -> dict:
    """{ (campaign, sensor, sensor_date): (wavelengths, fwhms) } ordered by band."""
    if df_wl is None or any(c not in df_wl.columns for c in list(SENSOR_CAMPAIGN_KEY) + ["band", "wavelength", "fwhm"]):
        return {}
    arrays = {}
    for _, grp in df_wl.groupby(list(SENSOR_CAMPAIGN_KEY)):
        key = row_key(grp.iloc[0], SENSOR_CAMPAIGN_KEY)
        try:
            arrays[key] = band_arrays(grp)
        except (ValueError, TypeError):
            continue  # non-castable values are reported by the wavelengths check
    return arrays


def _summary(data: dict) -> dict:
    """Bundle summary counts; a file that wasn't provided counts as 0."""
    def nunique(slot, col):
        df = data[slot]
        return int(df[col].nunique()) if df is not None and col in df.columns else 0

    def nrows(slot):
        return int(len(data[slot])) if data[slot] is not None else 0

    gdf_plots = data["plots"]
    df_traits = data["traits"]
    plot_cols = ["campaign_name", "plot_name"]
    sample_key_cols = ["campaign_name", "plot_name", "collection_date", "sample_name"]
    unique_plots = (
        gdf_plots[plot_cols].drop_duplicates().shape[0]
        if gdf_plots is not None and all(c in gdf_plots.columns for c in plot_cols) else 0
    )
    existing_sample_cols = [c for c in sample_key_cols if df_traits is not None and c in df_traits.columns]
    unique_samples = int(df_traits.drop_duplicates(subset=existing_sample_cols).shape[0]) if existing_sample_cols else 0

    return {
        "campaigns":           nunique("campaign_metadata", "campaign_name"),
        "sensors":             nunique("campaign_metadata", "sensor_name"),
        "granules":            nunique("granule_metadata", "granule_id"),
        "plots":               unique_plots,
        "plot_granule_combos": nrows("plots"),
        "samples":             unique_samples,
        "traits":              nrows("traits"),
        "pixels":              nrows("spectra"),
        "dois":                nrows("doi"),
        "files_provided":      sorted(slot for slot, df in data.items() if df is not None),
    }
