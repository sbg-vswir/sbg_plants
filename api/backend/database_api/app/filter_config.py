# ============================================================================
# MASTER FIELD DEFINITIONS
# ============================================================================

# String fields that support multiple values (comma-separated or lists)
STRING_FIELDS = {
    "plot_name",
    "campaign_name",
    "sensor_name",
    "granule_id",
    "site_id",
    "sample_name",
    "trait",
    "units",
    "method",
    "handling",
    "error_type",
    "taxa",
    "veg_or_cover_type",
    "phenophase",
    "sample_fc_class",
    "plant_status",
    "plot_veg_type",
    "subplot_cover_method",
    "floristic_survey",
    "plot_method"
}

# Numeric fields that support single values, lists, or ranges
NUMERIC_FIELDS = {
    "value",
    "error",
    "sample_fc_percent",
    "pixel_id"
}

# Boolean fields
BOOLEAN_FIELDS = {
    "floristic_survey"
}

# Date fields
DATE_FIELDS = {
    "granule_date",
    "collection_date"
}

# Special fields (handled separately)
SPECIAL_FIELDS = {
    "geom",
    "start_date",
    "end_date"
}

# View-specific field mappings
VIEW_FIELD_CONFIG = {
    "plot_pixels_mv": {
        "allowed_fields": {
            "plot_name",
            "campaign_name",
            "sensor_name",
            "granule_id",
            "granule_date",
            "geom"
        },
        "date_column": "granule_date" 
    },
    "leaf_traits_view": {
        "allowed_fields": {
            "plot_name",
            "campaign_name",
            "sensor_name",
            "granule_id",
            "site_id",
            "sample_name",
            "trait",
            "value",
            "units",
            "method",
            "handling",
            "error",
            "error_type",
            "taxa",
            "veg_or_cover_type",
            "phenophase",
            "sample_fc_class",
            "sample_fc_percent",
            "plant_status",
            "plot_veg_type",
            "subplot_cover_method",
            "floristic_survey",
            "plot_method",
            "collection_date"
            "geom"
        },
        "date_column": "collection_date"
    },
    "extracted_spectra_view": {
        "allowed_fields": {
            "pixel_id"
        }
    }
}
