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
    "plot_method",
    "elevation_source"
}

# Numeric fields that support single values, lists, or ranges
NUMERIC_FIELDS = {
    "plot_id",
    "value",
    "error",
    "sample_fc_percent",
    "pixel_id",
    "lon",
    "lat",
    "elevation",
    "path_length",
    "to_sensor_azimuth",
    "to_sensor_zenith",
    "to_sun_azimuth",
    "to_sun_zenith",
    "solar_phase",
    "slope",
    "aspect",
    "cosine_i", 
    "utc_time",
    "glt_row",
    "glt_column"
}

# Boolean fields
BOOLEAN_FIELDS = {
    "floristic_survey",
    "shade_mask"
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
            "pixel_id", 
            "radiance",
            "lon",
            "lat",
            "elevation",
            "path_length",
            "to_sensor_azimuth",
            "to_sensor_zenith",
            "to_sun_azimuth",
            "to_sun_zenith",
            "solar_phase",
            "slope",
            "aspect",
            "cosine_i", 
            "utc_time",
            "granule_id"
        }
    },
    "extracted_metadata_view": {
        "allowed_fields": {
            "campaign_name",
            "sensor_name",
            "elevation_source",
            "wavelength_center",
            "fwhm"
        }   
    }
}
