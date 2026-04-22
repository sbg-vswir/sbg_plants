import React, { useState, useRef } from 'react';
import {
  Box, Stack, Button, CircularProgress, Alert,
  Typography, Divider, Paper, ToggleButtonGroup, ToggleButton,
} from '@mui/material';
import {
  Search as SearchIcon,
  NavigateBefore as PrevIcon,
  NavigateNext as NextIcon,
  Download as DownloadIcon,
  GraphicEq as SpectraIcon,
  RestartAlt as ResetIcon,
} from '@mui/icons-material';

import Navbar from '../components/Navbar';
import MapView from '../components/MapView';
import LinkedFilterPanel from '../components/LinkedFilterPanel';
import PlotSidePanel from '../components/PlotSidePanel';
import LinkedDataTable from '../components/LinkedDataTable';
import JobStatus from '../components/JobStatus';

import { useLinkedQuery } from '../hooks/useLinkedQuery';
import { useSpectraExtraction } from '../hooks/useSpectraExtraction';

function LinkedQueryPage() {
  const q = useLinkedQuery();
  const clearDrawnRef = useRef(null);

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
  const showPaging = q.totalPlots > 0 && (hasPrev || hasNext);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Navbar />

      {/* Two-column body — fills remaining height, each column scrolls independently */}
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden', mt: '56px' }}>

        {/* Left — filter panel, scrollable */}
        <Box
          sx={{
            width: 380,
            flexShrink: 0,
            borderRight: 1,
            borderColor: 'divider',
            overflowY: 'auto',
            p: 2,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
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
            onClick={q.handleApply}
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
            <Box>
              <Typography variant="body2" color="text.secondary">
                {q.totalPlots} plots matched
              </Typography>
            </Box>
          )}
        </Box>

        {/* Right — map + side panel + table, scrollable */}
        <Box sx={{ flex: 1, overflowY: 'auto', p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>

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

          {/* Main area: [map+table] beside [side panel] */}
          <Stack direction="row" spacing={2} alignItems="flex-start">

            {/* Left: map then action bar then table stacked */}
            <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
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
              />

              {/* Action bar — between map and table */}
              {hasResults && (
                <Paper elevation={1} sx={{ px: 2, py: 1.5 }}>
                  <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
                    <Button size="small" variant="outlined" startIcon={<PrevIcon />}
                      onClick={q.handlePrev} disabled={!hasPrev || q.loading}>
                      Prev
                    </Button>
                    <Typography variant="body2" color="text.secondary" sx={{ minWidth: 160, textAlign: 'center' }}>
                      {q.displayedOffset + 1}–{Math.min(q.displayedOffset + q.limit, q.totalPlots)} of {q.totalPlots} plots
                    </Typography>
                    <Button size="small" variant="outlined" endIcon={<NextIcon />}
                      onClick={q.handleNext} disabled={!hasNext || q.loading}>
                      Next
                    </Button>

                    <Box sx={{ flex: 1 }} />

                    {/* Pixel count display */}
                    {q.hasQueried && (
                      <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
                        {q.pagePixelCount.toLocaleString()} px (page) /{' '}
                        {q.pixelCountLoading ? '…' : (q.totalPixelCount ?? 0).toLocaleString()} px (total)
                      </Typography>
                    )}

                    {/* Radiance / Reflectance toggle */}
                    <ToggleButtonGroup
                      value={spectra.spectraType}
                      exclusive
                      onChange={(_, v) => { if (v) spectra.setSpectraType(v); }}
                      size="small"
                    >
                      <ToggleButton value="radiance"     sx={{ textTransform: 'none', fontSize: 12 }}>Radiance</ToggleButton>
                      <ToggleButton value="reflectance"  sx={{ textTransform: 'none', fontSize: 12 }}>Reflectance</ToggleButton>
                    </ToggleButtonGroup>

                     <Button variant="contained" size="small" color="secondary" startIcon={<SpectraIcon />}
                       onClick={spectra.handleExtractSpectra}
                       disabled={extractDisabled || spectra.isPolling || !q.hasQueried}>
                      Extract Spectra
                    </Button>
                     <Button variant="contained" size="small" startIcon={downloadLoading ? <CircularProgress size={14} color="inherit" /> : <DownloadIcon />}
                       onClick={handleDownloadCSV} disabled={downloadLoading || !q.hasQueried}>
                       Download CSV{q.totalCsvRows != null ? ` (${q.totalCsvRows.toLocaleString()} rows)` : q.hasQueried ? ' (…)' : ''}
                     </Button>
                  </Stack>
                </Paper>
              )}

              {/* Job status — above table */}
              <JobStatus
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
            </Box>

            {/* Right: side panel — sticky so it stays in view while scrolling */}
            {q.selectedPlotId && (
              <Box sx={{ position: 'sticky', top: 0, alignSelf: 'flex-start', flexShrink: 0 }}>
                <PlotSidePanel
                  plotId={q.selectedPlotId}
                  traits={q.selectedTraits}
                  granules={q.selectedGranules}
                  onClose={() => q.setSelectedPlotId(null)}
                />
              </Box>
            )}
          </Stack>
        </Box>
      </Box>
    </Box>
  );
}

export default LinkedQueryPage;
