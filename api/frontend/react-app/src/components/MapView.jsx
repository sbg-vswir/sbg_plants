import React, { useEffect, useState } from 'react';
import { Paper, Typography, Box, Stack, Chip, IconButton, Collapse } from '@mui/material';
import { Map as MapIcon, ExpandMore as ExpandMoreIcon, ExpandLess as ExpandLessIcon } from '@mui/icons-material';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fits the map to the bounds of the current GeoJSON data whenever it changes.
// Falls back to setView(center, zoom) when there's no data to fit.
function MapUpdater({ mapData, center, zoom }) {
  const map = useMap();

  useEffect(() => {
    if (!mapData?.features?.length) {
      map.setView(center, zoom);
      return;
    }
    try {
      const layer = L.geoJSON(mapData);
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
      }
    } catch {
      map.setView(center, zoom);
    }
  }, [mapData]); // eslint-disable-line react-hooks/exhaustive-deps

  return null;
}

// Style for query results — default Leaflet blue
const RESULT_STYLE = {};

// Style for uploaded GeoJSON filter boundary — red
const FILTER_STYLE = {
  color:       '#d32f2f',
  weight:      2,
  opacity:     1,
  fillColor:   '#d32f2f',
  fillOpacity: 0.2,
};

function MapView({ mapData, filterData, center, zoom, defaultCollapsed = false, height = 500 }) {
  const [resultKey, setResultKey]       = useState(0);
  const [filterKey, setFilterKey]       = useState(0);
  const [showResults, setShowResults]   = useState(true);
  const [showFilter, setShowFilter]     = useState(true);
  const [collapsed, setCollapsed]       = useState(defaultCollapsed);

  useEffect(() => { if (mapData)    { setResultKey(prev => prev + 1); setShowResults(true); } }, [mapData]);
  useEffect(() => { if (filterData) { setFilterKey(prev => prev + 1); setShowFilter(true);  } }, [filterData]);

  return (
    <Paper elevation={2} sx={{ mb: 3, overflow: 'hidden' }}>
      <Box sx={{ bgcolor: '#f5f5f5', p: 2, borderBottom: collapsed ? 'none' : '1px solid #ddd' }}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <MapIcon color="primary" />
          <Typography variant="h6">Map View</Typography>
          {mapData && !collapsed && (
            <Typography variant="caption" color="text.secondary">
              {mapData.features?.length || 0} features
            </Typography>
          )}
          <Box sx={{ flex: 1 }} />
          {!collapsed && filterData && (
            <Chip
              label="Filter boundary"
              size="small"
              onClick={() => setShowFilter(v => !v)}
              sx={{
                bgcolor:    showFilter ? '#d32f2f' : 'transparent',
                color:      showFilter ? 'white' : '#d32f2f',
                border:     '1px solid #d32f2f',
                cursor:     'pointer',
                fontWeight: 500,
              }}
            />
          )}
          {!collapsed && mapData && (
            <Chip
              label="Query results"
              size="small"
              onClick={() => setShowResults(v => !v)}
              sx={{
                bgcolor:    showResults ? '#1976d2' : 'transparent',
                color:      showResults ? 'white' : '#1976d2',
                border:     '1px solid #1976d2',
                cursor:     'pointer',
                fontWeight: 500,
              }}
            />
          )}
          <IconButton size="small" onClick={() => setCollapsed(v => !v)}>
            {collapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
          </IconButton>
        </Stack>
      </Box>
      <Collapse in={!collapsed}>
        <Box sx={{ height }}>
          <MapContainer
            center={center}
            zoom={zoom}
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            />
            <MapUpdater mapData={mapData ?? filterData} center={center} zoom={zoom} />
            {filterData && showFilter  && <GeoJSON data={filterData} key={filterKey}  style={FILTER_STYLE} />}
            {mapData    && showResults && <GeoJSON data={mapData}    key={resultKey}   style={RESULT_STYLE} />}
          </MapContainer>
        </Box>
      </Collapse>
    </Paper>
  );
}

export default MapView;
