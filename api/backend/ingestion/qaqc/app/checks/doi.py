"""
QAQC checks for doi.csv

One row per DOI per thing it covers. A row is a rule: "cite this DOI when the
query results contain X". role says what part of the data it covers and the
scope columns (sensor_name, plot_method, trait, trait_method, site_ids) narrow
it; a blank scope means the whole campaign. A header-only file is valid.

Checks (in order):
  1. Mechanical — required columns, no missing values, enum values.
                  Driven by checks/config/doi.json. pk_cols is intentionally
                  empty — duplicates are checked in step 5 after normalizing.
  2. Normalize site_ids — split on ';', trim, dedupe and sort, written back to
                          the DataFrame so the staging load sees one form.
  3. Format — doi must be a bare DOI (10.xxxx/...), no https://doi.org/ prefix.
  4. Scope rules per role — mirrors doi_scope_chk in schema/plants_v5_tables.sql.
  5. Duplicates — (campaign_name, lower(doi), role, scopes) must be unique,
                  mirroring the doi_unique index.
  6. Campaign exists — campaign_name must be in this bundle's campaign_metadata
                       or already in production.
  7. Scopes exist — each sensor / plot_method / trait (+method) / site must
                    appear in this bundle or in production, otherwise the DOI
                    never shows.
  8. Existing DOI rows — a row already in production (doi_unique key) follows
                         the reuse-if-identical rule on citation_text.
  9. Site coverage (warning) — when a campaign's plot DOIs use site_ids, every
                               plot site in this bundle should be covered by
                               one of them.
"""

from __future__ import annotations

import re

import pandas as pd

from app.checks.types import CheckContext, CheckResult
from app.checks.universal import (
    load_config, run_mechanical_checks, check_foreign_key, check_existing_identical,
)
from app.db_refs import DOI_KEY, DOI_REQUIRED

CONFIG = load_config("doi")
CONFIG["_file_name"] = "doi"

# mirrors doi_scope_chk in schema/plants_v5_tables.sql — keep in sync
# role: (required scope cols, optional scope cols); any other role allows none
ROLE_SCOPES = {
    "radiance_dataset": (set(),                     {"sensor_name"}),
    "pixel_shade_mask": (set(),                     {"sensor_name"}),
    "plot_information": (set(),                     {"site_ids"}),
    "plot_shapes":      (set(),                     {"site_ids"}),
    "plot_method":      (set(),                     {"plot_method"}),
    "trait_method":     ({"trait", "trait_method"}, set()),
    "trait_data":       ({"trait"},                 {"trait_method"}),
}
SCOPE_COLS = ["sensor_name", "plot_method", "trait", "trait_method", "site_ids"]
SITE_ROLES = ("plot_information", "plot_shapes")
DOI_RE     = re.compile(r"^10\.[0-9]{4,9}/\S+$")


def check(context: CheckContext) -> CheckResult:
    df = context.data["doi"]
    errors, warnings = run_mechanical_checks(df, context.enums, CONFIG)
    if any("missing required columns" in e["message"] for e in errors):
        return CheckResult("doi", len(df), errors, warnings)

    for col in ["citation_text"] + SCOPE_COLS:
        if col not in df.columns:
            df[col] = ""

    _normalize_site_ids(df)
    errors += _check_format(df)
    errors += _check_scope_rules(df)
    errors += _check_duplicates(df)
    errors += _check_campaign_exists(df, context)
    errors += _check_scopes_exist(df, context)
    existing_errors, existing_warnings, existing = check_existing_identical(
        df, DOI_KEY, {"citation_text": "str"}, context.db["doi_rows"], "doi", "doi row",
        required=DOI_REQUIRED,
    )
    errors   += existing_errors
    warnings += existing_warnings
    context.output.setdefault("existing", {})["doi"] = existing
    warnings += _check_site_coverage(df, context)
    return CheckResult("doi", len(df), errors, warnings)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_set(val) -> bool:
    return not (pd.isna(val) or str(val).strip() == "")


def _split_sites(val) -> list[str]:
    return [s for s in str(val).split(";") if s] if _is_set(val) else []


def _plot_props(context: CheckContext) -> pd.DataFrame:
    """Plot feature properties from plots.geojson (no geometry); empty if not provided."""
    gdf = context.data.get("plots")
    if gdf is None or gdf.empty:
        return pd.DataFrame(columns=["campaign_name", "site_id", "plot_method"])
    return pd.DataFrame(gdf.drop(columns=gdf.geometry.name))


# ── Custom checks ──────────────────────────────────────────────────────────────

def _normalize_site_ids(df: pd.DataFrame) -> None:
    """Split on ';', trim, dedupe and sort so 'W02; W01;W01' becomes 'W01;W02'."""
    df["site_ids"] = df["site_ids"].apply(
        lambda v: ";".join(sorted({s.strip() for s in str(v).split(";") if s.strip()}))
        if _is_set(v) else ""
    )


def _check_format(df: pd.DataFrame) -> list[dict]:
    """doi must be a bare DOI — 10.xxxx/... without a URL or 'doi:' prefix."""
    errors = []
    for idx, row in df.iterrows():
        doi_val = str(row["doi"]).strip()
        if doi_val and not DOI_RE.match(doi_val):
            errors.append({
                "file": "doi", "row": int(idx + 2), "column": "doi",
                "message": (
                    f"'{doi_val}' is not a bare DOI — use the form 10.xxxx/..., "
                    f"without https://doi.org/ or doi:"
                ),
            })
    return errors


def _check_scope_rules(df: pd.DataFrame) -> list[dict]:
    """Required scopes are set and any scope the role doesn't allow is blank."""
    errors = []
    for idx, row in df.iterrows():
        required, optional = ROLE_SCOPES.get(row["role"], (set(), set()))
        missing   = [c for c in SCOPE_COLS if c in required and not _is_set(row[c])]
        forbidden = [c for c in SCOPE_COLS if c not in required | optional and _is_set(row[c])]
        if missing:
            errors.append({
                "file": "doi", "row": int(idx + 2), "column": None,
                "message": f"role '{row['role']}' requires: {', '.join(missing)}",
            })
        if forbidden:
            errors.append({
                "file": "doi", "row": int(idx + 2), "column": None,
                "message": f"role '{row['role']}' does not allow: {', '.join(forbidden)} (leave blank)",
            })
    return errors


def _check_duplicates(df: pd.DataFrame) -> list[dict]:
    """
    (campaign_name, lower(doi), role, scopes) must be unique — mirrors the
    doi_unique index. Runs after site_ids is normalized, so the same sites in
    a different order count as a duplicate.
    """
    key = df[["campaign_name", "role"] + SCOPE_COLS].assign(_doi=df["doi"].str.strip().str.lower())
    dupes = key[key.duplicated(keep=False)]
    if dupes.empty:
        return []
    errors = []
    for _, group in dupes.groupby(list(dupes.columns), dropna=False):
        rows = ", ".join(str(idx + 2) for idx in group.index)
        errors.append({
            "file": "doi", "row": None, "column": "doi",
            "message": f"doi '{df.loc[group.index[0], 'doi']}' is listed more than once with the same role and scope (rows: {rows})",
        })
    return errors


def _check_campaign_exists(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """campaign_name must be in this bundle's campaign_metadata or already in production."""
    df_campaign = context.data.get("campaign_metadata")
    bundle_campaigns = set(df_campaign.get("campaign_name", [])) if df_campaign is not None else set()
    return check_foreign_key(
        df, ["campaign_name"], bundle_campaigns | context.db["campaign_names"], "doi", "campaign_name",
    )


def _check_scopes_exist(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """A scope that matches nothing in the bundle or production would never be cited."""
    plots  = _plot_props(context)
    traits = context.data.get("traits")
    if traits is None:
        traits = pd.DataFrame(columns=["campaign_name", "trait", "method"])
    if "trait" in traits.columns:
        traits = traits[traits["trait"].astype(str).str.strip() != ""]  # skip sample-only rows

    # sensor scopes cover every sensor_date of the sensor, so compare on (campaign, sensor)
    sensor_set = {
        k[:2] for k in context.output.get("campaign_sensor_set", set()) | context.db["campaign_sensor_set"]
    }
    db_plots = context.db["plot_rows"]
    db_trait_keys = context.db["leaf_trait_rows"].keys()  # (campaign, plot, date, sample, trait, method, …)
    plot_method_set = set(zip(plots.get("campaign_name", []), plots.get("plot_method", []))) | {
        (k[0], v["plot_method"]) for k, v in db_plots.items()
    }
    site_set = set(zip(plots.get("campaign_name", []), plots.get("site_id", []))) | {
        (k[0], v["site_id"]) for k, v in db_plots.items()
    }
    trait_set = set(zip(traits.get("campaign_name", []), traits.get("trait", []))) | {
        (k[0], k[4]) for k in db_trait_keys
    }
    trait_method_set = set(zip(
        traits.get("campaign_name", []), traits.get("trait", []), traits.get("method", []),
    )) | {(k[0], k[4], k[5]) for k in db_trait_keys}

    errors = []

    def err(idx, column, message):
        errors.append({"file": "doi", "row": int(idx + 2), "column": column, "message": message})

    for idx, row in df.iterrows():
        camp = row["campaign_name"]
        if _is_set(row["sensor_name"]) and (camp, row["sensor_name"]) not in sensor_set:
            err(idx, "sensor_name", f"sensor '{row['sensor_name']}' is not in campaign_metadata.csv or the database for campaign '{camp}'")
        if _is_set(row["plot_method"]) and (camp, row["plot_method"]) not in plot_method_set:
            err(idx, "plot_method", f"no plots in plots.geojson or the database use plot_method '{row['plot_method']}' for campaign '{camp}'")
        if _is_set(row["trait"]):
            if (camp, row["trait"]) not in trait_set:
                err(idx, "trait", f"trait '{row['trait']}' is not in traits.csv or the database for campaign '{camp}'")
            elif _is_set(row["trait_method"]) and (camp, row["trait"], row["trait_method"]) not in trait_method_set:
                err(idx, "trait_method", f"trait '{row['trait']}' measured with method '{row['trait_method']}' is not in traits.csv or the database for campaign '{camp}'")
        for site in _split_sites(row["site_ids"]):
            if (camp, site) not in site_set:
                err(idx, "site_ids", f"site '{site}' is not in plots.geojson or the database for campaign '{camp}'")
    return errors


def _check_site_coverage(df: pd.DataFrame, context: CheckContext) -> list[dict]:
    """
    Warning: when any of a campaign's plot_information / plot_shapes DOIs use
    site_ids, every plot site should be covered — otherwise that site's plots
    get no citation for that role. A row with blank site_ids covers all sites.
    """
    plots = _plot_props(context)
    sites_by_campaign: dict[str, set] = {}
    for camp, site in zip(plots.get("campaign_name", []), plots.get("site_id", [])):
        sites_by_campaign.setdefault(camp, set()).add(site)

    warnings = []
    site_rows = df[df["role"].isin(SITE_ROLES)]
    for (camp, role), group in site_rows.groupby(["campaign_name", "role"]):
        if not group["site_ids"].apply(_is_set).any():
            continue
        if not group["site_ids"].apply(_is_set).all():
            continue  # a blank-site_ids row already covers every site
        covered   = {s for v in group["site_ids"] for s in _split_sites(v)}
        uncovered = sorted(sites_by_campaign.get(camp, set()) - covered)
        if uncovered:
            warnings.append({
                "file": "doi", "row": None, "column": "site_ids",
                "message": (
                    f"campaign '{camp}': sites with no '{role}' DOI: {', '.join(uncovered)} "
                    f"— their plots will have no {role} citation"
                ),
            })
    return warnings
