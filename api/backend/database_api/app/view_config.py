# ============================================================================
# VIEW_CONFIG — single source of truth for all database views.
#
# To add a new view, add one entry here. No other backend files need changing.
#
# Each view entry:
#   has_geo     (bool)  — whether the view has a geometry column
#   is_async    (bool)  — whether queries are dispatched via SQS
#   date_column (str)   — column used for start_date/end_date range filters
#                         (omit if the view has no date range filter)
#   columns     (dict)  — every column the view exposes:
#       type        : "string" | "numeric" | "boolean" | "date" | "geom"
#       filterable  : True if the column can be used as a filter
#       selectable  : True if the column can be requested in a SELECT
# ============================================================================

VIEW_CONFIG = {
    "plot_pixels_mv": {
        "has_geo":     True,
        "is_async":    False,
        "date_column": "granule_date",
        "columns": {
            "plot_id":                  {"type": "numeric", "filterable": False, "selectable": True},
            "plot_name":                {"type": "string",  "filterable": True,  "selectable": True},
            "campaign_name":            {"type": "string",  "filterable": True,  "selectable": True},
            "sensor_name":              {"type": "string",  "filterable": True,  "selectable": True},
            "granule_id":               {"type": "string",  "filterable": True,  "selectable": True},
            "granule_date":             {"type": "date",    "filterable": True,  "selectable": True},
            "acquisition_date":         {"type": "date",    "filterable": True,  "selectable": True},
            "cloudy_conditions":        {"type": "string",  "filterable": True,  "selectable": True},
            "cloud_type":               {"type": "string",  "filterable": True,  "selectable": True},
            "gsd":                      {"type": "numeric", "filterable": True,  "selectable": True},
            "extraction_method":        {"type": "string",  "filterable": True,  "selectable": True},
            "delineation_method":       {"type": "string",  "filterable": True,  "selectable": True},
            "shape_aligned_to_granule": {"type": "boolean", "filterable": True,  "selectable": True},
            "pixel_ids":                {"type": "string",  "filterable": False, "selectable": True},
            "geom":                     {"type": "geom",    "filterable": True,  "selectable": True},
        },
    },
    "leaf_traits_view": {
        "has_geo":     True,
        "is_async":    False,
        "date_column": "collection_date",
        "columns": {
            "campaign_name":       {"type": "string",  "filterable": True,  "selectable": True},
            "plot_id":             {"type": "numeric", "filterable": False, "selectable": True},
            "site_id":             {"type": "string",  "filterable": True,  "selectable": True},
            "plot_name":           {"type": "string",  "filterable": True,  "selectable": True},
            "sample_name":         {"type": "string",  "filterable": True,  "selectable": True},
            "collection_date":     {"type": "date",    "filterable": True,  "selectable": True},
            "trait":               {"type": "string",  "filterable": True,  "selectable": True},
            "value":               {"type": "numeric", "filterable": True,  "selectable": True},
            "units":               {"type": "string",  "filterable": True,  "selectable": True},
            "method":              {"type": "string",  "filterable": True,  "selectable": True},
            "handling":            {"type": "string",  "filterable": True,  "selectable": True},
            "error":               {"type": "numeric", "filterable": True,  "selectable": True},
            "error_type":          {"type": "string",  "filterable": True,  "selectable": True},
            "taxa":                {"type": "string",  "filterable": True,  "selectable": True},
            "veg_or_cover_type":   {"type": "string",  "filterable": True,  "selectable": True},
            "phenophase":          {"type": "string",  "filterable": True,  "selectable": True},
            "sample_fc_class":     {"type": "string",  "filterable": True,  "selectable": True},
            "sample_fc_percent":   {"type": "numeric", "filterable": True,  "selectable": True},
            "canopy_position":     {"type": "string",  "filterable": True,  "selectable": True},
            "plant_status":        {"type": "string",  "filterable": True,  "selectable": True},
            "plot_veg_type":       {"type": "string",  "filterable": True,  "selectable": True},
            "subplot_cover_method":{"type": "string",  "filterable": True,  "selectable": True},
            "floristic_survey":    {"type": "boolean", "filterable": True,  "selectable": True},
            "plot_method":         {"type": "string",  "filterable": True,  "selectable": True},
            "geom":                {"type": "geom",    "filterable": True,  "selectable": True},
        },
    },
    "extracted_spectra_view": {
        "has_geo":  False,
        "is_async": True,
        "columns": {
            "pixel_id":          {"type": "numeric", "filterable": True,  "selectable": True},
            "campaign_name":     {"type": "string",  "filterable": True,  "selectable": True},
            "sensor_name":       {"type": "string",  "filterable": True,  "selectable": True},
            "granule_id":        {"type": "string",  "filterable": True,  "selectable": True},
            "plot_id":           {"type": "numeric", "filterable": True,  "selectable": True},
            "plot_name":         {"type": "string",  "filterable": True,  "selectable": True},
            "lon":               {"type": "numeric", "filterable": True,  "selectable": True},
            "lat":               {"type": "numeric", "filterable": True,  "selectable": True},
            "elevation":         {"type": "numeric", "filterable": True,  "selectable": True},
            "path_length":       {"type": "numeric", "filterable": True,  "selectable": True},
            "to_sensor_azimuth": {"type": "numeric", "filterable": True,  "selectable": True},
            "to_sensor_zenith":  {"type": "numeric", "filterable": True,  "selectable": True},
            "to_sun_azimuth":    {"type": "numeric", "filterable": True,  "selectable": True},
            "to_sun_zenith":     {"type": "numeric", "filterable": True,  "selectable": True},
            "solar_phase":       {"type": "numeric", "filterable": True,  "selectable": True},
            "slope":             {"type": "numeric", "filterable": True,  "selectable": True},
            "aspect":            {"type": "numeric", "filterable": True,  "selectable": True},
            "cosine_i":          {"type": "numeric", "filterable": True,  "selectable": True},
            "utc_time":          {"type": "numeric", "filterable": True,  "selectable": True},
            "shade_mask":        {"type": "boolean", "filterable": True,  "selectable": True},
            "radiance":          {"type": "numeric", "filterable": False, "selectable": True},
        },
    },
    "reflectance_view": {
        "has_geo":  False,
        "is_async": True,
        "columns": {
            "pixel_id":          {"type": "numeric", "filterable": True,  "selectable": True},
            "campaign_name":     {"type": "string",  "filterable": True,  "selectable": True},
            "sensor_name":       {"type": "string",  "filterable": True,  "selectable": True},
            "granule_id":        {"type": "string",  "filterable": True,  "selectable": True},
            "plot_id":           {"type": "numeric", "filterable": True,  "selectable": True},
            "plot_name":         {"type": "string",  "filterable": True,  "selectable": True},
            "lon":               {"type": "numeric", "filterable": True,  "selectable": True},
            "lat":               {"type": "numeric", "filterable": True,  "selectable": True},
            "elevation":         {"type": "numeric", "filterable": True,  "selectable": True},
            "cloudy_conditions": {"type": "string",  "filterable": True,  "selectable": True},
            "cloud_type":        {"type": "string",  "filterable": True,  "selectable": True},
            "reflectance":       {"type": "numeric", "filterable": False, "selectable": True},
        },
    },
    "extracted_metadata_view": {
        "has_geo":  False,
        "is_async": False,
        "columns": {
            "campaign_name":    {"type": "string",  "filterable": True,  "selectable": True},
            "sensor_name":      {"type": "string",  "filterable": True,  "selectable": True},
            "elevation_source": {"type": "string",  "filterable": True,  "selectable": True},
            "wavelength_center":{"type": "numeric", "filterable": False, "selectable": True},
            "fwhm":             {"type": "numeric", "filterable": False, "selectable": True},
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers — used by query.py, filter.py, filter_utils.py, main.py
# ---------------------------------------------------------------------------

def get_selectable_columns(view_name: str) -> list:
    return [col for col, cfg in VIEW_CONFIG[view_name]["columns"].items() if cfg["selectable"]]


def get_filterable_columns(view_name: str) -> set:
    return {col for col, cfg in VIEW_CONFIG[view_name]["columns"].items() if cfg["filterable"]}


def get_field_type(view_name: str, col: str) -> str:
    return VIEW_CONFIG[view_name]["columns"][col]["type"]


def get_date_column(view_name: str):
    return VIEW_CONFIG[view_name].get("date_column")
