import dash
from dash import Dash, html, dcc, dash_table, Input, Output, State
import dash_leaflet as dl
import pandas as pd
import io
import requests
import base64
import json
import geopandas as gpd
from shapely import wkt, geometry
import numpy as np
from itertools import chain

from view_config import VIEW_CONFIGS, SELECT_CONFIGS

app = Dash(__name__, suppress_callback_exceptions=True)

PAGE_SIZE = 100  # rows per page

views = list(VIEW_CONFIGS.keys())

app.layout = html.Div([
    html.H2("VSWIR Plants"),
    html.Div(id="dummy"),
    # Dropdown for views
    html.Label("Select View:"),
    dcc.Dropdown(
        id="view-dropdown",
        options=[{"label": v, "value": v} for v in views],
        value="plot-pixels_mv"
    ),

    # Dynamic filter container
    html.Div(id="filter-container", style={"margin": "10px 0"}),

    html.Div([
        html.Label("Upload GeoJSON (optional):"),
        dcc.Upload(
            id="geojson-upload",
            children=html.Div(["Drag and Drop or ", html.A("Select Files")]),
            multiple=False
        ),
        html.Div(id="geojson-filename", style={"marginTop": "5px", "fontStyle": "italic"})
    ], style={"margin": "10px 0"}),


   
    dcc.Store(id="offset-store", data=0),  # Holds current offset
    dcc.Store(id="filter-clicks-store", data=0),  # Track filter button clicks
    dcc.Store(id="next-clicks-store", data=0),    # Track next button clicks
    
    # Next button
    html.Button(f"Next {PAGE_SIZE}", id="next-button", disabled=True),
    
    html.Button(f"Reset", id="reset-button"),
    
    html.Button(f"Extract Spectra", id="extract-spectra", disabled=True),
    
    html.Button("Apply Filters", id="filter-button", disabled=True),
    
     # 2. Text field to show the returned job_id
    html.Div(id="job-id-display", children="Job ID will appear here"),

    html.Div(id="rows-processed-display", children="Rows processed: 0"),
    
    # 3. Hidden store to keep job_id
    dcc.Store(id="job-id-store"),

    # 4. Interval to poll the endpoint every X seconds
    dcc.Interval(id="poll-interval", interval=1*1000, disabled=True),  


    html.A(
        "Download Spectra",
        id="download-button",
        href="#",
        target="_blank",
        download="data.csv",
        className="btn btn-primary",
        style={"pointer-events": "none", "opacity": 0.5},  # disabled initially
    ),     
    
    # Map
    dl.Map(
        id="map",
        style={'width': '75%', 'height': '500px', 'margin': '0 auto'},
        zoom=2,
        center=[0, 0],
        children=[dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")]
    ),
    
    html.Button(
        "Download Table",
        id="download-table-button",
        className="btn btn-primary",
        n_clicks=0,
        disabled = True
    ),
    dcc.Download(id="download-table"),
    
    # Table
    dash_table.DataTable(
        id="table",
        page_current=0,
        page_size=PAGE_SIZE,
        page_action="custom"
    ),

])


API_URL = "https://iuzni7mumj.execute-api.us-west-2.amazonaws.com/views/{}"

import base64
import json

def parse_filters(filter_ids, filter_values, geojson_content=None):
    filters = {}

    for i, filter_id in enumerate(filter_ids):
        field_name = filter_id["index"]
        field_value = filter_values[i]

        if field_value:
            if field_name == "plot_name":
                filters[field_name] = [p.strip() for p in field_value.split(",")]
            else:
                filters[field_name] = field_value
        else:
            filters[field_name] = None

    # Add polygon filter
    filters["geom"] = None

    # Handle uploaded GeoJSON
    if geojson_content:
        geojson_str = geojson_content.split(",")[1]
        geojson_bytes = base64.b64decode(geojson_str)
        filters["geom"] = json.loads(geojson_bytes)

    return filters



def to_ranges(sorted_values):
    """
    Convert a sorted list of integers into a list of (start, end) ranges.
    """
    ranges = []
    start = prev = sorted_values[0]

    for val in sorted_values[1:]:
        if val == prev + 1:
            # consecutive, extend the current range
            prev = val
        else:
            # end current range
            ranges.append((int(start), int(prev))) # cast as ints incase they are numpy ints
            start = prev = val
    ranges.append((int(start), int(prev)))
    return ranges


def fetch_parquet(view, filters, geojson_content=None, limit=None, offset=0):
    """
    Fetch Parquet from API using filters, optional GeoJSON, with limit & offset.
    """
    
    select = SELECT_CONFIGS[view]
    
    payload  = {"view": view, "format": "parquet", "select": select, "offset": offset, "debug": True}
    
    if limit is not None and isinstance(limit, int):
        payload ['limit'] = limit
        
    valid_filters = {k: v for k, v in filters.items() if v is not None}
    if valid_filters:
        payload["filters"] = valid_filters
    print(filters)
    print('-------------------------------')  

    resp = requests.post(API_URL.format(view), json=payload)
    resp.raise_for_status()
    df = gpd.read_parquet(io.BytesIO(resp.content))
    
    return df

def summarize_value(v, n=2, *args, **kwargs):
    if isinstance(v, np.ndarray):
        v = v.tolist()
    if isinstance(v, (list, tuple)):
        if len(v) <= 2 * n:
            return str(v)
        return f"[{', '.join(map(str, v[:n]))}, ..., {', '.join(map(str, v[-n:]))}]"
    return v


@app.callback(
    Output("job-id-display", "children", allow_duplicate=True),
    Output("job-id-store", "data", allow_duplicate=True),
    Output("poll-interval", "disabled", allow_duplicate=True),
    Output("extract-spectra", "disabled", allow_duplicate=True),
    Input("extract-spectra", "n_clicks"),
    State("table", "data"),
    State("offset-store", "data"),
    State("filter-clicks-store", "data"),
    State("next-clicks-store", "data"),
    State("view-dropdown", "value"),
    State({"type": "filter-input", "index": dash.dependencies.ALL}, "value"),
    State({"type": "filter-input", "index": dash.dependencies.ALL}, "id"),
    State("geojson-upload", "contents"),
    prevent_initial_call=True
)
def extract_spectra(n_clicks, table_data, offset, stored_filter_clicks, stored_next_clicks,
                     view, filter_values, filter_ids, geojson_content):
    
    if n_clicks is None or not table_data:
        raise dash.exceptions.PreventUpdate

    filters = parse_filters(filter_ids, filter_values, geojson_content)
    
    # this might need to be a chunked operation in the future
    df_page = fetch_parquet(view, filters, geojson_content)
    pixel_ids = set(chain.from_iterable(df_page['pixel_ids']))
    if len(pixel_ids) == 0:
        return "Job ID will appear here", "", True, True
    
    pixel_ranges = to_ranges(sorted(pixel_ids))
    spectral_filters = {'pixel_id': pixel_ranges}
    params = {"view": "extracted_spectra_view", "format": "parquet", "debug": True}
    
    valid_spectral_filters = {
        k: v for k, v in spectral_filters.items() if len(v) > 0
    }
     
    params['filters'] = valid_spectral_filters
    
    resp = requests.post(API_URL.format("extracted_spectra_view"), json=params)
    print(resp.status_code)
    print(resp.json())
    resp.raise_for_status()
   
    job_id = resp.json()['job_id']
    
    return f"Job ID: {job_id}", job_id, False, True
    

@app.callback(
    Output("rows-processed-display", "children", allow_duplicate=True),
    Output("download-button", "href", allow_duplicate=True),
    Output("download-button", "style", allow_duplicate=True),
    Output("poll-interval", "disabled", allow_duplicate=True),
    Input("poll-interval", "n_intervals"),
    State("job-id-store", "data"),
    prevent_initial_call=True
)
def poll_job(n_intervals, job_id):
    if not job_id:
        raise dash.exceptions.PreventUpdate

    base_url = "https://iuzni7mumj.execute-api.us-west-2.amazonaws.com/job_status/{}"
    response = requests.get(base_url.format(job_id))

    # Job not created yet → keep polling
    if response.status_code == 404:
        return (
            "Job queued…",
            "#",
            {"pointer-events": "none", "opacity": 0.5},
            False,  # keep polling
        )

    # Real error
    if response.status_code != 200:
        return (
            "Error fetching job status",
            "#",
            {"pointer-events": "none", "opacity": 0.5},
            True,  # stop polling
        )

    data = response.json()

    rows = data.get("rows_processed", 0)
    presigned_url = data.get("presigned_url")

    rows_text = f"Rows processed: {rows}"

    if presigned_url:
        # Job complete → enable download + stop polling
        return (
            rows_text,
            presigned_url,
            {"pointer-events": "auto", "opacity": 1},
            True,
        )

    # Job still running
    return (
        rows_text,
        "#",
        {"pointer-events": "none", "opacity": 0.5},
        False,
    )
    
@app.callback(
    Output("geojson-filename", "children"),
    Input("geojson-upload", "filename")
)
def show_filename(filename):
    if filename is None:
        return ""
    return f"Selected file: {filename}"
    
@app.callback(
    Output("filter-container", "children", allow_duplicate=True),
    Output("table", "data", allow_duplicate=True),
    Output("table", "columns", allow_duplicate=True),
    Output("map", "children", allow_duplicate=True),
    Output("map", "center", allow_duplicate=True),
    Output("map", "zoom", allow_duplicate=True),
    Output("next-button", "disabled", allow_duplicate=True),
    Output("offset-store", "data", allow_duplicate=True),
    Output("filter-clicks-store", "data", allow_duplicate=True),
    Output("next-clicks-store", "data", allow_duplicate=True),
    Output("view-dropdown", "value"),
    Output("extract-spectra", "disabled", allow_duplicate=True),
    Output("download-table-button", "disabled", allow_duplicate=True),
    Output("job-id-display", "children", allow_duplicate=True),
    Output("rows-processed-display", "children", allow_duplicate=True),
    Output("job-id-store", "data", allow_duplicate=True),
    Output("poll-interval", "disabled", allow_duplicate=True),
    Output("poll-interval", "n_intervals", allow_duplicate=True),
    Output("download-button", "style", allow_duplicate=True),
    Output("geojson-filename", "children", allow_duplicate=True),
    Input("reset-button", "n_clicks"),
    prevent_initial_call=True
)
def reset(view):
    empty_map = [dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")]
    default_center = [0, 0]
    default_zoom = 2
    
    return html.Div("No filters available for this view."), [], [], empty_map, default_center, default_zoom, True, 0, 0, 0, "", True, True, "Job ID will appear here", "Rows processed: 0",None,  True,  0, {"pointer-events": "none", "opacity": 0.5}, ""

@app.callback(
    Output("filter-container", "children", allow_duplicate=True),
    Output("table", "data", allow_duplicate=True),
    Output("table", "columns", allow_duplicate=True),
    Output("map", "children", allow_duplicate=True),
    Output("map", "center", allow_duplicate=True),
    Output("map", "zoom", allow_duplicate=True),
    Output("next-button", "disabled", allow_duplicate=True),
    Output("offset-store", "data", allow_duplicate=True),
    Output("filter-clicks-store", "data", allow_duplicate=True),
    Output("next-clicks-store", "data", allow_duplicate=True),
    Output("filter-button", "disabled", allow_duplicate=True),
    Input("view-dropdown", "value"),
    prevent_initial_call=True
)
def update_filters(view):
    """Dynamically generate filter inputs based on selected view and reset table."""
    if view not in VIEW_CONFIGS:
        empty_map = [dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")]
        default_center = [0, 0]
        default_zoom = 2
        
        return html.Div("No filters available for this view."), [], [], empty_map, default_center, default_zoom, True, 0, 0, 0, True
    
    
    filter_config = VIEW_CONFIGS[view]["filters"]
    filter_elements = []
    
    for f in filter_config:
        filter_elements.extend([
            html.Label(f["label"]),
            dcc.Input(
                id={"type": "filter-input", "index": f["id"]},
                type=f["type"],
                placeholder=f["placeholder"]
            )
        ])
    
    # Empty map (just base tile layer)
    empty_map = [dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")]
    default_center = [0, 0]
    default_zoom = 2
 
    return filter_elements, [], [], empty_map, default_center, default_zoom, True, 0, 0, 0, False


@app.callback(
    Output("filter-button", "disabled", allow_duplicate=True),
    Input("filter-button", "n_clicks"),
    prevent_initial_call=True
)
def disable_apply_filters(n_clicks):
    if n_clicks > 0:
        return True
 

@app.callback(
    Output("table", "data"),
    Output("table", "columns"),
    Output("map", "children"),
    Output("offset-store", "data"),
    Output("extract-spectra", "disabled", allow_duplicate=True),
    Output("next-button", "disabled", allow_duplicate=True),
    Output("filter-button", "disabled", allow_duplicate=True),
    Output("download-table-button", "disabled", allow_duplicate=True),
    Input("filter-button", "n_clicks"),
    Input("next-button", "n_clicks"),
    State("offset-store", "data"),
    State("filter-clicks-store", "data"),
    State("next-clicks-store", "data"),
    State("view-dropdown", "value"),
    State({"type": "filter-input", "index": dash.dependencies.ALL}, "value"),
    State({"type": "filter-input", "index": dash.dependencies.ALL}, "id"),
    State("geojson-upload", "contents"),
    prevent_initial_call=True
)
def update_table_map(filter_clicks, next_clicks, offset, stored_filter_clicks, stored_next_clicks,
                     view, filter_values, filter_ids, geojson_content):
    
    ctx = dash.callback_context

    # Determine which button was clicked
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    # Only proceed if a button was actually clicked (not just state changes)
    if triggered_id not in ["filter-button", "next-button"]:
        raise dash.exceptions.PreventUpdate
    
    # Check if clicks actually increased (not just carried over from before view change)
    if triggered_id == "filter-button":
        if filter_clicks is None or filter_clicks <= stored_filter_clicks:
            raise dash.exceptions.PreventUpdate
        offset = 0
    elif triggered_id == "next-button":
        if next_clicks is None or next_clicks <= stored_next_clicks:
            raise dash.exceptions.PreventUpdate
        offset = offset + PAGE_SIZE
       
    filters = parse_filters(filter_ids, filter_values, geojson_content)

    # Fetch only the page we want
    df_page = fetch_parquet(view, filters, geojson_content, limit=PAGE_SIZE, offset=offset)
    df_page["id"] = range(offset, offset + PAGE_SIZE)
    cols = ["id"] + [c for c in df_page.columns if c != "id"]
    df_page = df_page[cols]
    # --- Table ---
    table_df = df_page.drop(columns=["geom"], errors="ignore").copy()
    for col in table_df.columns:
        table_df[col] = table_df[col].apply(summarize_value)
    table_columns = [{"name": c, "id": c} for c in table_df.columns]
    table_data = table_df.to_dict("records")

    # --- Map ---
    map_children = [dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")]
    if "geom" in df_page.columns and not df_page["geom"].isnull().all():
        features = []
        for _, row in df_page.iterrows():
            geom = row["geom"]
            if pd.notnull(geom):
                if isinstance(geom, str):
                    geom = wkt.loads(geom)
                if isinstance(geom, geometry.base.BaseGeometry):
                    geom = geom.__geo_interface__
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {k: summarize_value(row[k]) for k in df_page.columns if k != "geom"}
                })
        geojson_data = {"type": "FeatureCollection", "features": features}
        map_children.append(dl.GeoJSON(data=geojson_data))

    # disable extract spectra here for now
    enable_extract = not bool(len(table_data)) or (view == 'leaf_traits_view')
    enable_next = not bool(len(table_data))
    
    return table_data, table_columns, map_children, offset, enable_extract, enable_next, False, False

@app.callback(
    Output("download-table", "data"),
    Input("download-table-button", "n_clicks"),
    State("view-dropdown", "value"),
    State({"type": "filter-input", "index": dash.dependencies.ALL}, "value"),
    State({"type": "filter-input", "index": dash.dependencies.ALL}, "id"),
    State("geojson-upload", "contents"),
    prevent_initial_call=True
)
def download_table(n_clicks, view, filter_values, filter_ids, geojson_content):
    filters = parse_filters(filter_ids, filter_values, geojson_content)
    df = fetch_parquet(view, filters, geojson_content)
    return dcc.send_data_frame(df.to_csv, "table_data.csv", index=False)



if __name__ == "__main__":
    app.run(debug=True)