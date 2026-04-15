import React, { useState } from 'react';
import {
  Paper, Typography, TextField, Button, Box, Stack, Chip,
  Autocomplete, ToggleButton, ToggleButtonGroup, IconButton, Tooltip,
} from '@mui/material';
import {
  FilterAlt as FilterIcon,
  NavigateNext as NextIcon,
  Download as DownloadIcon,
  RestartAlt as ResetIcon,
  CalendarMonth as CalendarIcon,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { parse, isValid } from 'date-fns';

// Auto-formats a raw keystroke string into YYYY-MM-DD as the user types.
// Normalizes / to -, strips invalid chars, auto-inserts - after year and month.
function formatDateInput(raw) {
  // normalize separators and strip anything that isn't a digit or -
  let val = raw.replace(/\//g, '-').replace(/[^\d-]/g, '');

  // auto-insert - after year (position 4) if user just typed the 5th digit
  if (val.length === 5 && !val.includes('-')) {
    val = val.slice(0, 4) + '-' + val.slice(4);
  }
  // auto-insert - after month (position 7) if user just typed the 8th digit
  if (val.length === 8 && val.indexOf('-', 5) === -1) {
    val = val.slice(0, 7) + '-' + val.slice(7);
  }

  return val.slice(0, 10);
}

function DateFilterInput({ filter, value, onFilterChange }) {
  const [inputText, setInputText] = useState(
    value ? value.toISOString().slice(0, 10) : ''
  );
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(false);
  const anchorRef = React.useRef(null);

  const tryParse = (text) => {
    if (!text) {
      onFilterChange(filter.id, null);
      setError(false);
      return;
    }
    const parsed = parse(text, 'yyyy-MM-dd', new Date());
    if (isValid(parsed) && text.length === 10) {
      onFilterChange(filter.id, parsed);
      setError(false);
    } else if (text.length === 10) {
      setError(true);
    } else {
      setError(false);
    }
  };

  const handleTextChange = (e) => {
    const formatted = formatDateInput(e.target.value);
    setInputText(formatted);
    tryParse(formatted);
  };

  const handleBlur = () => {
    tryParse(inputText);
  };

  const handleCalendarChange = (newValue) => {
    if (newValue && isValid(newValue)) {
      const iso = newValue.toISOString().slice(0, 10);
      setInputText(iso);
      onFilterChange(filter.id, newValue);
      setError(false);
    }
    setOpen(false);
  };

  return (
    <Box sx={{ position: 'relative' }} ref={anchorRef}>
      <TextField
        label={filter.label}
        value={inputText}
        onChange={handleTextChange}
        onBlur={handleBlur}
        placeholder="YYYY-MM-DD"
        size="small"
        fullWidth
        error={error}
        helperText={error ? 'Use YYYY-MM-DD' : ''}
        InputProps={{
          endAdornment: (
            <IconButton size="small" onClick={() => setOpen(true)} tabIndex={-1}>
              <CalendarIcon fontSize="small" />
            </IconButton>
          ),
        }}
      />
      <DatePicker
        open={open}
        onClose={() => setOpen(false)}
        value={value || null}
        onChange={handleCalendarChange}
        slotProps={{
          textField: { sx: { display: 'none' } },
          popper: { anchorEl: anchorRef.current },
        }}
      />
    </Box>
  );
}

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
              <DateFilterInput
                key={filter.id}
                filter={filter}
                value={filterValues[filter.id] || null}
                onFilterChange={onFilterChange}
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