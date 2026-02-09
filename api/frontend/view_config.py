
VIEW_CONFIGS = {
    "plot_pixels_mv": {
        "filters": [
            {"id": "plot_name", "label": "Plot Name (comma-separated):", "type": "text", 
             "placeholder": "e.g., 276-ER18,001-ER18"},
            {"id": "campaign_name", "label": "Campaign Name:", "type": "text", 
             "placeholder": "e.g., East River 2018"},
            {"id": "sensor_name", "label": "Sensor Name:", "type": "text", 
             "placeholder": "e.g., NEON AIS 1"},
            {"id": "granule_id", "label": "Granule ID:", "type": "text", 
             "placeholder": "e.g., NIS01_20180621_172130"},
            {"id": "start_date", "label": "Start Date:", "type": "text", 
             "placeholder": "YYYY-MM-DD"},
            {"id": "end_date", "label": "End Date:", "type": "text", 
             "placeholder": "YYYY-MM-DD"},
        ]
    },
    "leaf_traits_view": {
        "filters": [
            {"id": "campaign_name", "label": "Campaign Name:", "type": "text", 
             "placeholder": "e.g., East River 2018"},
            {"id": "site_id", "label": "Site ID:", "type": "text", 
             "placeholder": "e.g., ER"},
            {"id": "plot_name", "label": "Plot Name (comma-separated):", "type": "text", 
             "placeholder": "e.g., 276-ER18,001-ER18"},
            {"id": "sample_name", "label": "Sample Name:", "type": "text", 
             "placeholder": "e.g., SAMPLE001"},
            {"id": "collection_date", "label": "Collection Date:", "type": "text", 
             "placeholder": "YYYY-MM-DD"},
            {"id": "trait", "label": "Trait:", "type": "text", 
             "placeholder": "e.g., leaf_area, chlorophyll"},
            {"id": "taxa", "label": "Taxa:", "type": "text", 
             "placeholder": "e.g., Salix planifolia"},
            {"id": "veg_or_cover_type", "label": "Vegetation/Cover Type:", "type": "text", 
             "placeholder": "e.g., shrub, forb"},
            {"id": "phenophase", "label": "Phenophase:", "type": "text", 
             "placeholder": "e.g., flowering, senescent"},
            {"id": "plant_status", "label": "Plant Status:", "type": "text", 
             "placeholder": "e.g., live, dead"},
            {"id": "plot_veg_type", "label": "Plot Vegetation Type:", "type": "text", 
             "placeholder": "e.g., riparian"},
            {"id": "start_date", "label": "Start Date:", "type": "text", 
             "placeholder": "YYYY-MM-DD"},
            {"id": "end_date", "label": "End Date:", "type": "text", 
             "placeholder": "YYYY-MM-DD"},
        ]
    }
}

SELECT_CONFIGS = {
    "plot_pixels_mv": [
        'plot_name',
        'campaign_name',
        'sensor_name',
        'granule_id',
        'granule_date',
        'pixel_ids',
        'geom'  
    ],
    "leaf_traits_view": [
        'campaign_name',
        'site_id',
        'plot_name',
        'sample_name',
        'collection_date',
        'trait',
        'value',
        'units',
        'method',
        'handling',
        'error',
        'error_type',
        'taxa',
        'veg_or_cover_type',
        'phenophase',
        'sample_fc_class',
        'sample_fc_percent',
        'plant_status',
        'plot_veg_type',
        'subplot_cover_method',
        'floristic_survey',
        'plot_method',
        'geom'
    ],
    "extracted_spectra_view": [
        "pixel_id"
    ]
}