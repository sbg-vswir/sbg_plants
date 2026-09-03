# ============================================================================
# ENUM_KEY_MAP — single source of truth for which Postgres enum types are
# exposed by this API, and what key they're exposed as.
#
# Left side  : Postgres enum type name (schema "vswir_plants")
#              — see schema/plants_v5_types.sql
# Right side : the key the frontend's viewConfig.js ENUMS dict already uses.
#
# Most of these are just a lowercase of the Postgres type name, but a few
# don't follow that convention and must be mapped explicitly:
#   VEGETATION_type    -> plot_veg_type
#   FRACTIONAL_class   -> sample_fc_class
#   Sample_handling    -> handling
#   CLOUD_conditions   -> cloudy_conditions
#
# Only types listed here are returned by GET /enums. Postgres enum types that
# exist but aren't currently used as a frontend filter (ELEVATION_source,
# Error_type, Repository, Trait_units) are intentionally omitted.
#
# Adding a new VALUE to an existing enum (e.g. a new taxa species) requires
# no change here or in the frontend — it just shows up on the next request.
# Adding a brand new enum CATEGORY still requires: an entry here, a matching
# entry in viewConfig.js's ENUMS, and a filter definition wherever it should
# be used.
#
# This module plays the same role here that view_config.py's VIEW_CONFIG
# plays for the main database_api Lambda: a hardcoded whitelist that query.py
# binds as a parameter, rather than trusting anything dynamic.
# ============================================================================

SCHEMA_NAME = "vswir_plants"

ENUM_KEY_MAP = {
    "TAXA":                  "taxa",
    "CAMPAIGN_name":         "campaign_name",
    "Sensor_name":           "sensor_name",
    "VEG_or_cover_type":     "veg_or_cover_type",
    "CANOPY_position":       "canopy_position",
    "PLANT_status":          "plant_status",
    "PHENOPHASE":            "phenophase",
    "VEGETATION_type":       "plot_veg_type",
    "FRACTIONAL_class":      "sample_fc_class",
    "SUBPLOT_cover_method":  "subplot_cover_method",
    "PLOT_method":           "plot_method",
    "CLOUD_conditions":      "cloudy_conditions",
    "CLOUD_type":            "cloud_type",
    "EXTRACTION_method":     "extraction_method",
    "DELINEATION_method":    "delineation_method",
    "Sample_handling":       "handling",
    "Trait":                 "trait",
    "Trait_method":          "trait_method",
}


def get_allowed_type_names() -> list:
    """The whitelist of Postgres enum type names this API is allowed to read."""
    return list(ENUM_KEY_MAP.keys())


def get_frontend_key(typname: str):
    """Map a Postgres enum type name to its frontend key, or None if not whitelisted."""
    return ENUM_KEY_MAP.get(typname)
