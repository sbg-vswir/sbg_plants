import React, { useRef, useState } from 'react';
import {
  Box, Typography, Stack, Divider,
  TextField, Autocomplete, Chip, Button,
  IconButton, Collapse,
} from '@mui/material';
import {
  FilterList as FilterIcon,
  Draw as DrawIcon,
  UploadFile as UploadIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import { ENUMS } from '../viewConfig';

function CollapsibleSection({ title, children }) {
  const [open, setOpen] = useState(true);
  return (
    <Box sx={{ mb: 1 }}>
      <Stack
        direction="row" alignItems="center" justifyContent="space-between"
        sx={{ cursor: 'pointer' }}
        onClick={() => setOpen(v => !v)}
      >
        <Typography variant="caption" color="text.secondary">{title}</Typography>
        <IconButton size="small" tabIndex={-1}>
          {open ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
        </IconButton>
      </Stack>
      <Divider sx={{ mb: open ? 2 : 0 }} />
      <Collapse in={open}>
        {children}
      </Collapse>
    </Box>
  );
}

function LinkedFilterPanel({
  campaignName, setCampaignName,
  traitFilters, setTraitFilters,
  granuleFilters, setGranuleFilters,
  geojsonContent, setGeojsonContent,
  clearDrawnRef,
}) {
  const setTF = (key) => (value) =>
    setTraitFilters(prev => ({ ...prev, [key]: value }));

  const setGF = (key) => (value) =>
    setGranuleFilters(prev => ({ ...prev, [key]: value }));

  const fileInputRef = useRef(null);

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const parsed = JSON.parse(evt.target.result);
        if (parsed.type === 'FeatureCollection') {
          const geom = parsed.features?.[0]?.geometry;
          if (geom) setGeojsonContent(geom);
        } else if (parsed.type === 'Feature') {
          setGeojsonContent(parsed.geometry);
        } else if (parsed.coordinates) {
          setGeojsonContent(parsed);
        } else {
          alert('Could not parse GeoJSON — expected a Geometry, Feature, or FeatureCollection.');
        }
      } catch {
        alert('Invalid JSON file.');
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <FilterIcon color="primary" />
        <Typography variant="h6">Filters</Typography>
      </Stack>

      {/* Campaign */}
      <TextField
        label="Campaign name"
        size="small"
        fullWidth
        value={campaignName}
        onChange={e => setCampaignName(e.target.value)}
        sx={{ mb: 2 }}
        placeholder="e.g. East River 2018"
      />

      {/* Spatial filter */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          Spatial filter
        </Typography>
        {geojsonContent ? (
          <Stack direction="row" spacing={1} alignItems="center">
            <DrawIcon fontSize="small" color="primary" />
            <Typography variant="body2" color="primary" sx={{ flex: 1 }}>
              Spatial filter active
            </Typography>
            <Button size="small" color="error" onClick={() => {
              clearDrawnRef?.current?.();
              setGeojsonContent(null);
            }}>
              Clear
            </Button>
          </Stack>
        ) : (
          <Stack direction="row" spacing={1}>
            <Typography variant="caption" color="text.secondary" sx={{ flex: 1, alignSelf: 'center' }}>
              Draw on map or upload a file
            </Typography>
            <Button
              size="small"
              variant="outlined"
              startIcon={<UploadIcon />}
              onClick={() => fileInputRef.current?.click()}
            >
              Upload GeoJSON
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,.geojson"
              style={{ display: 'none' }}
              onChange={handleFileUpload}
            />
          </Stack>
        )}
      </Box>

      {/* Trait filters — collapsible */}
      <CollapsibleSection title="Trait filters">
        <Stack spacing={2} sx={{ mb: 2 }}>
          <TextField
            label="Plot name"
            size="small"
            fullWidth
            value={traitFilters.plot_name ?? ''}
            onChange={e => setTF('plot_name')(e.target.value)}
            placeholder="e.g. 276-ER18"
          />
          <TextField
            label="Sample name"
            size="small"
            fullWidth
            value={traitFilters.sample_name ?? ''}
            onChange={e => setTF('sample_name')(e.target.value)}
            placeholder="e.g. 021-ER18_Salixwolfii"
          />
          <EnumField label="Trait"                  value={traitFilters.trait ?? []}                 onChange={setTF('trait')}                 options={ENUMS.trait} />
          <EnumField label="Taxa"                   value={traitFilters.taxa ?? []}                  onChange={setTF('taxa')}                  options={ENUMS.taxa} />
          <EnumField label="Vegetation / Cover type" value={traitFilters.veg_or_cover_type ?? []}    onChange={setTF('veg_or_cover_type')}     options={ENUMS.veg_or_cover_type} />
          <EnumField label="Phenophase"             value={traitFilters.phenophase ?? []}            onChange={setTF('phenophase')}            options={ENUMS.phenophase} />
          <EnumField label="Plant status"           value={traitFilters.plant_status ?? []}          onChange={setTF('plant_status')}          options={ENUMS.plant_status} />
          <EnumField label="Canopy position"        value={traitFilters.canopy_position ?? []}       onChange={setTF('canopy_position')}       options={ENUMS.canopy_position} />
          <EnumField label="Plot vegetation type"   value={traitFilters.plot_veg_type ?? []}         onChange={setTF('plot_veg_type')}         options={ENUMS.plot_veg_type} />
          <EnumField label="Subplot cover method"   value={traitFilters.subplot_cover_method ?? []}  onChange={setTF('subplot_cover_method')}  options={ENUMS.subplot_cover_method} />
          <EnumField label="Fractional cover class" value={traitFilters.sample_fc_class ?? []}       onChange={setTF('sample_fc_class')}       options={ENUMS.sample_fc_class} />
          <EnumField label="Sample handling"        value={traitFilters.handling ?? []}              onChange={setTF('handling')}              options={ENUMS.handling} />
          <EnumField label="Trait method"           value={traitFilters.method ?? []}                onChange={setTF('method')}                options={ENUMS.trait_method} />
          <Stack direction="row" spacing={1}>
            <TextField
              label="Collection date from"
              type="date" size="small" fullWidth
              InputLabelProps={{ shrink: true }}
              value={traitFilters.collection_date_start ?? ''}
              onChange={e => setTF('collection_date_start')(e.target.value)}
            />
            <TextField
              label="Collection date to"
              type="date" size="small" fullWidth
              InputLabelProps={{ shrink: true }}
              value={traitFilters.collection_date_end ?? ''}
              onChange={e => setTF('collection_date_end')(e.target.value)}
            />
          </Stack>
        </Stack>
      </CollapsibleSection>

      {/* Granule filters — collapsible */}
      <CollapsibleSection title="Granule filters">
        <Stack spacing={2}>
          <EnumField label="Sensor name"       value={granuleFilters.sensor_name ?? []}       onChange={setGF('sensor_name')}       options={ENUMS.sensor_name} />
          <EnumField label="Cloudy conditions" value={granuleFilters.cloudy_conditions ?? []} onChange={setGF('cloudy_conditions')} options={ENUMS.cloudy_conditions} />
          <EnumField label="Cloud type"        value={granuleFilters.cloud_type ?? []}        onChange={setGF('cloud_type')}        options={ENUMS.cloud_type} />
          <Stack direction="row" spacing={1}>
            <TextField
              label="Acquisition date from"
              type="date" size="small" fullWidth
              InputLabelProps={{ shrink: true }}
              value={granuleFilters.acquisition_date_start ?? ''}
              onChange={e => setGF('acquisition_date_start')(e.target.value)}
            />
            <TextField
              label="Acquisition date to"
              type="date" size="small" fullWidth
              InputLabelProps={{ shrink: true }}
              value={granuleFilters.acquisition_date_end ?? ''}
              onChange={e => setGF('acquisition_date_end')(e.target.value)}
            />
          </Stack>
        </Stack>
      </CollapsibleSection>
    </Box>
  );
}

function EnumField({ label, value, onChange, options = [] }) {
  return (
    <Autocomplete
      multiple
      size="small"
      options={options}
      value={value}
      onChange={(_, newValue) => onChange(newValue)}
      renderTags={(val, getTagProps) =>
        val.map((option, index) => (
          <Chip key={index} label={option} size="small" {...getTagProps({ index })} />
        ))
      }
      renderInput={(params) => (
        <TextField {...params} label={label} />
      )}
    />
  );
}

export default LinkedFilterPanel;
