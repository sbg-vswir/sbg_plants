import React, { useState, useRef } from 'react';
import {
  Box, Stack, Button, CircularProgress, Alert,
  Typography, Divider, Paper, ToggleButtonGroup, ToggleButton,
  Tooltip, IconButton, Drawer, useMediaQuery, useTheme,
} from '@mui/material';
import {
  Search as SearchIcon,
  NavigateBefore as PrevIcon,
  NavigateNext as NextIcon,
  Download as DownloadIcon,
  GraphicEq as SpectraIcon,
  RestartAlt as ResetIcon,
  ChevronLeft as CollapseIcon,
  ChevronRight as ExpandIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';

import Navbar from '../components/Navbar';
import MapView from '../components/MapView';
import LinkedFilterPanel from '../components/LinkedFilterPanel';
import PlotSidePanel from '../components/PlotSidePanel';
import LinkedDataTable from '../components/LinkedDataTable';
import CitationsPanel from '../components/CitationsPanel';
import SpectraJobStatus from '../components/SpectraJobStatus';
import StagingToggle from '../components/StagingToggle';
import SpectraControls from '../components/SpectraControls';

import { useLinkedQuery } from '../hooks/useLinkedQuery';
import { useSpectraExtraction } from '../hooks/useSpectraExtraction';

function LinkedQueryPage() {
  const q = useLinkedQuery();
  const clearDrawnRef = useRef(null);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const [filterCollapsed, setFilterCollapsed] = useState(false);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);
  const [extractDisabled, setExtractDisabled] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);

  const spectra = useSpectraExtraction(
    q.getPixelRanges,
    q.setError,
    setExtractDisabled,
  );

  const handleDownloadCSV = async () => {
    setDownloadLoading(true);
    try {
      const rows = await q.getMergedDownloadData();
      if (!rows.length) { q.setError('No data to download'); return; }
      const cols = Object.keys(rows[0]);
      const lines = [
        cols.join(','),
        ...rows.map(row =>
          cols.map(c => {
            const val = row[c];
            if (val === null || val === undefined) return '';
            const str = String(val);
            if (str.includes(',') || str.includes('"') || str.includes('\n')) {
              return `"${str.replace(/"/g, '""')}"`;
            }
            return str;
          }).join(',')
        ),
      ].join('\n');
      const blob = new Blob(['\uFEFF' + lines], { type: 'text/csv;charset=utf-8;' });
      const url  = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'linked_query.csv';
      document.body.appendChild(link);
      link.click();
      URL.revokeObjectURL(url);
      document.body.removeChild(link);
    } catch (err) {
      q.setError(err.message ?? 'Download failed');
    } finally {
      setDownloadLoading(false);
    }
  };

  const hasResults = q.totalPlots > 0 || q.traits.length > 0 || q.granules.length > 0;
  const hasPrev    = q.offset > 0;
  const hasNext    = q.totalPlots > q.offset + q.limit;

  const filterContent = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, px: 2, pb: 2, pt: isMobile ? 2 : 0, flex: 1, overflowY: 'auto' }}>
      <StagingToggle onToggle={() => { q.handleReset(); spectra.reset(); setExtractDisabled(false); clearDrawnRef?.current?.(); }} />
      <LinkedFilterPanel
        campaignName={q.campaignName}
        setCampaignName={q.setCampaignName}
        traitFilters={q.traitFilters}
        setTraitFilters={q.setTraitFilters}
        granuleFilters={q.granuleFilters}
        setGranuleFilters={q.setGranuleFilters}
        geojsonContent={q.geojsonContent}
        setGeojsonContent={q.setUploadedGeojson}
        clearDrawnRef={clearDrawnRef}
      />
      <Divider />
      <Button
        variant="contained"
        startIcon={q.loading ? <CircularProgress size={16} color="inherit" /> : <SearchIcon />}
        onClick={() => { q.handleApply(); if (isMobile) setMobileFilterOpen(false); }}
        disabled={q.loading}
        fullWidth
      >
        Apply
      </Button>
      <Button
        variant="contained"
        color="secondary"
        startIcon={<ResetIcon />}
        onClick={() => { q.handleReset(); spectra.reset(); setExtractDisabled(false); clearDrawnRef?.current?.(); }}
        disabled={q.loading}
        fullWidth
      >
        Reset
      </Button>
      {hasResults && (
        <Typography variant="body2" color="text.secondary">
          {q.totalPlots} plots matched
        </Typography>
      )}
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Navbar />

      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden', mt: '56px', maxWidth: { xl: 1920 }, mx: 'auto', width: '100%' }}>

        {/* Mobile — filter drawer */}
        {isMobile && (
          <Drawer
            anchor="left"
            open={mobileFilterOpen}
            onClose={() => setMobileFilterOpen(false)}
            PaperProps={{ sx: { width: 300, mt: '56px', height: 'calc(100% - 56px)' } }}
          >
            {filterContent}
          </Drawer>
        )}

        {/* Desktop — filter side panel */}
        {!isMobile && (
          <Box
            sx={{
              width: filterCollapsed ? 48 : { md: 300, lg: 380, xl: 420 },
              flexShrink: 0,
              borderRight: 1,
              borderColor: 'divider',
              overflowY: filterCollapsed ? 'hidden' : 'auto',
              overflowX: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              transition: 'width 0.2s ease',
            }}
          >
            <Box sx={{ display: 'flex', justifyContent: filterCollapsed ? 'center' : 'flex-end', p: 0.5, flexShrink: 0 }}>
              <Tooltip title={filterCollapsed ? 'Expand filters' : 'Collapse filters'} placement="right">
                <IconButton size="small" onClick={() => setFilterCollapsed(v => !v)}>
                  {filterCollapsed ? <ExpandIcon /> : <CollapseIcon />}
                </IconButton>
              </Tooltip>
            </Box>
            {!filterCollapsed && filterContent}
            {filterCollapsed && (
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, pt: 1 }}>
                <Tooltip title="Filters" placement="right">
                  <FilterIcon fontSize="small" color="action" />
                </Tooltip>
                {hasResults && (
                  <Tooltip title={`${q.totalPlots} plots matched`} placement="right">
                    <Typography variant="caption" color="primary" sx={{ writingMode: 'vertical-rl', fontSize: 10 }}>
                      {q.totalPlots}
                    </Typography>
                  </Tooltip>
                )}
              </Box>
            )}
          </Box>
        )}

        {/* Right — map + table */}
        <Box sx={{ flex: 1, overflowY: 'auto', p: { xs: 1, sm: 2 }, display: 'flex', flexDirection: 'column', gap: 2, position: 'relative', minWidth: 0 }}>

          {/* Mobile filter toggle button */}
          {isMobile && (
            <Button
              variant="outlined"
              startIcon={<FilterIcon />}
              onClick={() => setMobileFilterOpen(true)}
              size="small"
              sx={{ alignSelf: 'flex-start' }}
            >
              Filters{hasResults ? ` · ${q.totalPlots} plots` : ''}
            </Button>
          )}

          {q.error && (
            <Alert severity="error" onClose={() => q.setError(null)}>{q.error}</Alert>
          )}
          {Object.entries(spectra.sensorStatuses ?? {}).some(([, s]) => s.error) && (
            <Alert severity="error">
              {Object.entries(spectra.sensorStatuses)
                .filter(([, s]) => s.error)
                .map(([key, s]) => `${key}: ${s.error}`)
                .join(' | ')}
            </Alert>
          )}

          {q.loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
              <CircularProgress />
            </Box>
          )}

          {!q.loading && q.hasQueried && q.totalPlots === 0 && (
            <Alert severity="info">No plots matched your filters.</Alert>
          )}

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {q.selectedPlotId && (
              <PlotSidePanel
                plotId={q.selectedPlotId}
                traits={q.selectedTraits}
                granules={q.selectedGranules}
                onClose={() => q.setSelectedPlotId(null)}
              />
            )}

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <MapView
                mapData={q.mapData}
                filterData={q.filterMapData}
                center={[39.5, -106]}
                zoom={6}
                onFeatureClick={q.setSelectedPlotId}
                selectedPlotId={q.selectedPlotId}
                onShapeDrawn={q.setDrawnGeojson}
                clearDrawnRef={clearDrawnRef}
                drawnShape={q.geojsonContent && q.geojsonIsDrawn ? q.geojsonContent : null}
                height={isMobile ? 280 : 420}
              />

              {hasResults && (
                <SpectraControls
                  q={q}
                  spectra={spectra}
                  hasPrev={hasPrev}
                  hasNext={hasNext}
                  extractDisabled={extractDisabled}
                  downloadLoading={downloadLoading}
                  onDownloadCSV={handleDownloadCSV}
                  isMobile={isMobile}
                />
              )}

              <SpectraJobStatus
                jobsBySensor={spectra.jobsBySensor ?? {}}
                sensorStatuses={spectra.sensorStatuses ?? {}}
              />

              {hasResults && (
                <LinkedDataTable
                  traits={q.traits}
                  granules={q.granules}
                  totalTraits={q.totalTraits}
                  totalGranules={q.totalGranules}
                />
              )}

              {hasResults && <CitationsPanel citations={q.citations} />}
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}

export default LinkedQueryPage;
