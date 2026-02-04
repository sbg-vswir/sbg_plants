
import dash
from dash import Dash, html, dcc, dash_table, Input, Output, State
import dash_leaflet as dl
import pandas as pd
import io
import requests
import base64
import pyarrow.parquet as pq
import geopandas as gpd
import base64, json
from shapely import wkt, geometry
import numpy as np
from view_config import VIEW_CONFIGS

app = Dash(__name__, suppress_callback_exceptions=True)

PAGE_SIZE = 100  # rows per page

views = list(VIEW_CONFIGS.keys())

app.layout = html.Div([
    html.H2("VSWIR Plants"),

    # Dropdown for views
    html.Label("Select View:"),
    dcc.Dropdown(
        id="view-dropdown",
        options=[{"label": v, "value": v} for v in views],
        value="plot-pixels_mv"
    ),

    # Dynamic filter container
    html.Div(id="filter-container", style={"margin": "10px 0"}),

    # GeoJSON file upload (optional)
    html.Div([
        html.Label("Upload GeoJSON (optional):"),
        dcc.Upload(
            id="geojson-upload",
            children=html.Div(["Drag and Drop or ", html.A("Select Files")]),
            multiple=False
        )
    ], style={"margin": "10px 0"}),

   
    dcc.Store(id="offset-store", data=0),  # Holds current offset
    dcc.Store(id="filter-clicks-store", data=0),  # Track filter button clicks
    dcc.Store(id="next-clicks-store", data=0),    # Track next button clicks
    
    # Next button
    html.Button(f"Next {PAGE_SIZE}", id="next-button", disabled=True),
    
    html.Button(f"Reset", id="reset-button"),
    
    # Map
    dl.Map(
        id="map",
        style={'width': '75%', 'height': '500px', 'margin': '0 auto'},
        zoom=2,
        center=[0, 0],
        children=[dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")]
    ),

    # Table
    dash_table.DataTable(
        id="table",
        page_current=0,
        page_size=PAGE_SIZE,
        page_action="custom"
    ),

])


API_URL = "https://iuzni7mumj.execute-api.us-west-2.amazonaws.com/views/{}"


def fetch_parquet(view, filters, geojson_content=None, limit=100, offset=0):
    """
    Fetch Parquet from API using filters, optional GeoJSON, with limit & offset.
    """
    params = {"view": view, "format": "parquet", "limit": limit, "offset": offset, "debug": True}

    valid_filters = {}
    for k, v in filters.items():
        if v is None:
            continue
        if isinstance(v, list):
            valid_filters[k] = ",".join(v)
        else:
            valid_filters[k] = str(v)
            
    params['filters'] = json.dumps(valid_filters)
    
    if geojson_content:
        geojson_str = geojson_content.split(",")[1]
        print(geojson_str)
        # geojson_bytes = base64.b64decode(geojson_str)
        # files = {"geojson": ("upload.geojson", geojson_bytes, "application/json")}
        # resp = requests.post(API_URL.format(view), params=params, files=files)
    else:
        resp = requests.get(API_URL.format(view), params=params)

    print(params)
    resp.raise_for_status()
    df = gpd.read_parquet(io.BytesIO(resp.content))
    # print(df)
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
    Input("reset-button", "n_clicks"),
    prevent_initial_call=True
)
def reset(view):
    empty_map = [dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")]
    default_center = [0, 0]
    default_zoom = 2
    
    return html.Div("No filters available for this view."), [], [], empty_map, default_center, default_zoom, True, 0, 0, 0, ""

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
    Input("view-dropdown", "value"),
    prevent_initial_call=True
)
def update_filters(view):
    """Dynamically generate filter inputs based on selected view and reset table."""
    if view not in VIEW_CONFIGS:
        empty_map = [dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")]
        default_center = [0, 0]
        default_zoom = 2
        
        return html.Div("No filters available for this view."), [], [], empty_map, default_center, default_zoom, True, 0, 0, 0
    
    
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
    
    # add apply filter button
    filter_elements.append(html.Button("Apply Filters", id="filter-button"))
    
    # Empty map (just base tile layer)
    empty_map = [dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")]
    default_center = [0, 0]
    default_zoom = 2
 
    return filter_elements, [], [], empty_map, default_center, default_zoom, True, 0, 0, 0


@app.callback(
    Output("next-button", "disabled", allow_duplicate=True),
    Input("filter-button", "n_clicks"),
    prevent_initial_call=True
)
def enable_next(n_clicks):
    if n_clicks and n_clicks > 0:
        return False  # enable button
    return True       # keep disabled


@app.callback(
    Output("table", "data"),
    Output("table", "columns"),
    Output("map", "children"),
    Output("offset-store", "data"),
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
       
     
    # Build filters dict dynamically from the pattern-matching inputs
    filters = {}
    for i, filter_id in enumerate(filter_ids):
        field_name = filter_id["index"]
        field_value = filter_values[i]
        
        if field_value:
            # Handle comma-separated values for plot_name
            if field_name == "plot_name":
                filters[field_name] = [p.strip() for p in field_value.split(",")]
            else:
                filters[field_name] = [field_value]
        else:
            filters[field_name] = None

    # Add polygon filter
    filters["polygon"] = None

    # Handle uploaded GeoJSON
    if geojson_content:
        geojson_str = geojson_content.split(",")[1]
        geojson_bytes = base64.b64decode(geojson_str)
        filters["polygon"] = json.loads(geojson_bytes)

    # Fetch only the page we want
    df_page = fetch_parquet(view, filters, geojson_content, limit=PAGE_SIZE, offset=offset)

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


    return table_data, table_columns, map_children, offset


if __name__ == "__main__":
    app.run(debug=True)