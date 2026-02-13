import React, { useEffect, useState } from 'react';
import { Paper, Typography, Box, Stack } from '@mui/material';
import { Map as MapIcon } from '@mui/icons-material';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Helper component to update map view
function MapUpdater({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center && zoom) {
      map.setView(center, zoom);
    }
  }, [center, zoom, map]);
  return null;
}

function MapView({ mapData, center, zoom }) {
  const [geoJsonKey, setGeoJsonKey] = useState(0);
  
  useEffect(() => {
    if (mapData) {
      setGeoJsonKey(prev => prev + 1);
    }
  }, [mapData]);
  
  return (
    <Paper elevation={2} sx={{ mb: 3, overflow: 'hidden' }}>
      <Box sx={{ bgcolor: '#f5f5f5', p: 2, borderBottom: '1px solid #ddd' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <MapIcon color="primary" />
          <Typography variant="h6">Map View</Typography>
          {mapData && (
            <Typography variant="caption">
              {mapData.features?.length || 0} features
            </Typography>
          )}
        </Stack>
      </Box>
      <Box sx={{ height: 500 }}>
        <MapContainer
          center={center}
          zoom={zoom}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />
          <MapUpdater center={center} zoom={zoom} />
          {mapData && <GeoJSON data={mapData} key={geoJsonKey} />}
        </MapContainer>
      </Box>
    </Paper>
  );
}

export default MapView;