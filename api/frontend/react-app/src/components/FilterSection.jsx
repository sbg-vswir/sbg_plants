import React from 'react';
import {
  Paper,
  Typography,
  TextField,
  Button,
  Box,
  Stack,
  Chip
} from '@mui/material';
import {
  FilterAlt as FilterIcon,
  NavigateNext as NextIcon,
  Science as ScienceIcon,
  Download as DownloadIcon
} from '@mui/icons-material';

const PAGE_SIZE = 100;

function FilterSection({
  filters,
  filterValues,
  onFilterChange,
  geojsonFile,
  onGeojsonUpload,
  onApplyFilters,
  onNext,
  onExtractSpectra,
  onDownloadTable,
  loading,
  nextDisabled,
  extractDisabled,
  downloadTableDisabled
}) {
  return (
    <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <FilterIcon color="primary" />
        <Typography variant="h6">Filters</Typography>
      </Stack>
      
      {/* Filter Inputs */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 2, mb: 3 }}>
        {filters.map(filter => (
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
        ))}
      </Box>

      {/* GeoJSON Upload */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Upload GeoJSON (optional)
        </Typography>
        <input
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
      <Stack direction="row" spacing={2} flexWrap="wrap">
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
          Next {PAGE_SIZE}
        </Button>
        <Button
          variant="contained"
          color="secondary"
          startIcon={<ScienceIcon />}
          onClick={onExtractSpectra}
          disabled={extractDisabled || loading}
        >
          Extract Spectra
        </Button>
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
