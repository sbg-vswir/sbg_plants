import React from 'react';
import {
  Paper, Typography, TextField, Button, Box, Stack, Chip,
  Autocomplete, ToggleButton, ToggleButtonGroup, IconButton, Tooltip,
} from '@mui/material';
import {
  FilterAlt as FilterIcon,
  NavigateNext as NextIcon,
  Download as DownloadIcon,
  RestartAlt as ResetIcon,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';

function FilterSection({
  filters,
  filterValues,
  onFilterChange,
  geojsonFile,
  geojsonKey,
  onGeojsonUpload,
  onApplyFilters,
  onNext,
  pageSize,
  onExtractSpectra,
  onDownloadTable,
  loading,
  nextDisabled,
  extractDisabled,
  downloadTableDisabled,
  extractLabel = 'Extract Spectra',
  spectraType = 'radiance',
  onSpectraTypeChange,
  lockSpectraType = false,
  // view selector
  view,
  views,
  onViewChange,
  onReset,
  hideExtract = false,
}) {
  return (
    <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <FilterIcon color="primary" />
        <Typography variant="h6">Filters</Typography>
        <Box sx={{ flex: 1 }} />
        {onReset && (
          <Tooltip title="Reset">
            <IconButton size="small" onClick={onReset}>
              <ResetIcon />
            </IconButton>
          </Tooltip>
        )}
      </Stack>

      {/* View selector */}
      {views && views.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <ToggleButtonGroup
            value={view}
            exclusive
            onChange={(_, val) => { if (val) onViewChange(val); }}
            size="small"
          >
            {views.map(v => (
              <ToggleButton key={v.key} value={v.key} sx={{ textTransform: 'none', px: 2 }}>
                {v.label}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Box>
      )}
      {/* Filter Inputs */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 2, mb: 3 }}>
        {filters.map(filter => {
          if (filter.type === 'date') {
            return (
                <DatePicker
                  key={filter.id}
                  label={filter.label}
                  value={filterValues[filter.id] || null}
                  onChange={(newValue) => onFilterChange(filter.id, newValue)}
                  slotProps={{ textField: { size: 'small', fullWidth: true } }}
                />
            );
          }
          else if (filter.type === 'enum' && filter.options) {
            return (
              <Autocomplete
                key={filter.id}
                multiple
                options={filter.options}
                value={filterValues[filter.id] || []}
                onChange={(e, newValue) => onFilterChange(filter.id, newValue)}
                renderInput={(params) => (
                  <TextField {...params} label={filter.label} size="small" />
                )}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => {
                    const { key, ...tagProps } = getTagProps({ index });
                    return <Chip key={key} label={option} size="small" {...tagProps} />;
                  })
                }
                fullWidth
              />
            );
          } else {
            return (
              <TextField
                key={filter.id}
                label={filter.label}
                type={filter.type}
                placeholder={filter.placeholder}
                value={filterValues[filter.id] || ''}
                onChange={(e) => onFilterChange(filter.id, e.target.value)}
                size="small"
                fullWidth
              />
            );
          }
        })}
      </Box>

      {/* GeoJSON Upload */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Upload GeoJSON (optional)
        </Typography>
        <input
          key={geojsonKey}
          type="file"
          accept=".geojson,.json"
          onChange={onGeojsonUpload}
          style={{ marginBottom: '8px' }}
        />
        {geojsonFile && (
          <Chip 
            label={`Selected: ${geojsonFile.name}`} 
            size="small" 
            color="primary" 
            variant="outlined"
            sx={{ ml: 2 }}
          />
        )}
      </Box>

      {/* Action Buttons */}
      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap sx={{ rowGap: 1.5 }} alignItems="center">
        <Button
          variant="contained"
          startIcon={<FilterIcon />}
          onClick={onApplyFilters}
          disabled={loading}
        >
          Apply Filters
        </Button>
        <Button
          variant="outlined"
          startIcon={<NextIcon />}
          onClick={onNext}
          disabled={nextDisabled || loading}
        >
          Next {pageSize}
        </Button>
        {!hideExtract && (
          <>
            <ToggleButtonGroup
              value={spectraType}
              exclusive
              onChange={(_, val) => { if (val && onSpectraTypeChange) onSpectraTypeChange(val); }}
              size="small"
              disabled={lockSpectraType}
            >
              <ToggleButton value="radiance" sx={{ textTransform: 'none', px: 2 }}>
                Radiance
              </ToggleButton>
              <ToggleButton value="reflectance" sx={{ textTransform: 'none', px: 2 }}>
                Reflectance
              </ToggleButton>
            </ToggleButtonGroup>
            <Button
              variant="contained"
              color="secondary"
              onClick={onExtractSpectra}
              disabled={extractDisabled || loading}
            >
              {extractLabel}
            </Button>
          </>
        )}
        <Button
          variant="outlined"
          startIcon={<DownloadIcon />}
          onClick={onDownloadTable}
          disabled={downloadTableDisabled || loading}
        >
          Download Table
        </Button>
      </Stack>
    </Paper>
  );
}

export default FilterSection;