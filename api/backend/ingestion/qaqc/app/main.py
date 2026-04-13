import logging

from app.db import get_connection, load_enums
from app.s3_files import download_raw_files, parse_files, write_report
from app.dynamo import update_status
from app.db_refs import load_all as load_db_refs
from app.staging import load_all as load_staging
from app.checks.types import CheckContext
from app.checks.runner import run_all as run_checks

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
    raw_files = download_raw_files(batch_id)

    try:
        df_campaign, df_wl, df_granule, df_traits, df_spectra, geojson = parse_files(raw_files)
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
    # Pre-compute bundle band counts and seed them into context.output before
    # the runner starts, so spectra.py can look them up alongside the DB counts.
    bundle_band_counts = {
        (camp, sens): len(grp)
        for (camp, sens), grp in df_wl.groupby(["campaign_name", "sensor_name"])
    }

    context = CheckContext(
        enums=enums,
        db=db,
        data={
            "campaign_metadata": df_campaign,
            "wavelengths":       df_wl,
            "granule_metadata":  df_granule,
            "plots":             geojson,
            "traits":            df_traits,
            "spectra":           df_spectra,
        },
        output={
            # Seed band counts so SpectraCheck can find them even if
            # WavelengthsCheck hasn't explicitly forwarded them.
            "bundle_band_counts": bundle_band_counts,
        },
    )

    report, has_errors = run_checks(context)

    # ── 4. Write full report to S3 ────────────────────────────────────────────
    final_status = "QAQC_FAIL" if has_errors else "QAQC_PASS"
    s3_key       = write_report(batch_id, final_status, report)

    if has_errors:
        logger.info("QAQC FAIL for batch_id=%s", batch_id)
        update_status(batch_id, "QAQC_FAIL", report, s3_key)
        return

    # ── 5. Load into staging ──────────────────────────────────────────────────
    logger.info("QAQC PASS — loading into staging for batch_id=%s", batch_id)

    # Attach wavelength arrays to campaign df for sensor_campaign staging insert
    wl_arrays   = {}
    fwhm_arrays = {}
    for (camp, sens), grp in df_wl.groupby(["campaign_name", "sensor_name"]):
        grp_sorted = grp.assign(_band_int=grp["band"].astype(int)).sort_values("_band_int")
        wl_arrays[(camp, sens)]   = grp_sorted["wavelength"].astype(float).tolist()
        fwhm_arrays[(camp, sens)] = grp_sorted["fwhm"].astype(float).tolist()

    df_campaign["wavelength_center"] = df_campaign.apply(
        lambda r: wl_arrays.get((r["campaign_name"], r["sensor_name"]), []), axis=1
    )
    df_campaign["fwhm"] = df_campaign.apply(
        lambda r: fwhm_arrays.get((r["campaign_name"], r["sensor_name"]), []), axis=1
    )

    dfs = {
        "campaign_metadata": df_campaign,
        "granule_metadata":  df_granule,
        "traits":            df_traits,
        "spectra":           df_spectra,
        "plots_props":       [f["properties"] for f in geojson.get("features", [])],
    }

    row_counts = load_staging(conn, batch_id, dfs, geojson)
    logger.info("Staging load complete: %s", row_counts)

    for table, count in row_counts.items():
        if table in report:
            report[table]["staged_rows"] = count

    update_status(batch_id, "QAQC_PASS", report, s3_key)
    logger.info("QAQC complete for batch_id=%s", batch_id)
