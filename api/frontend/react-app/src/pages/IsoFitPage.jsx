import React from 'react';
import { Container, Box, CircularProgress, Alert, Stack } from '@mui/material';
import Navbar from '../components/Navbar';
import FilterSection from '../components/FilterSection';
import IsoFitStatus from '../components/IsoFitStatus';
import IsoFitHistory from '../components/IsoFitHistory';
import MapView from '../components/MapView';
import DataTable from '../components/DataTable';
import { VIEW_CONFIGS } from '../viewConfig';
import { summarizeValue } from '../utils/helpers';
import { useDataQuery } from '../hooks/useDataQuery';
import { useIsoFitJob } from '../hooks/useIsoFitJob';

function IsoFitPage() {
  const [view, setView] = React.useState('plot_pixels_mv');
  const query  = useDataQuery(view);
  const isofit = useIsoFitJob(
    query.getPixelRanges,
    query.setError,
    query.setExtractDisabled,
  );

  const handleViewChange = (e) => {
    setView(e.target.value);
    query.reset();
  };

  const handleReset = () => {
    setView('plot_pixels_mv');
    query.reset();
    isofit.reset();
  };

  const views             = Object.keys(VIEW_CONFIGS);
  const currentViewConfig = VIEW_CONFIGS[view] || { filters: [] };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Navbar
        view={view}
        views={views}
        onViewChange={handleViewChange}
        onReset={handleReset}
      />
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <Stack direction={{ xs: 'column', lg: 'row' }} spacing={3} alignItems="flex-start">

          {/* ── Left — filter + job status ────────────────────────────── */}
          <Box sx={{ width: { xs: '100%', lg: 420 }, flexShrink: 0 }}>
            <FilterSection
              filters={currentViewConfig.filters}
              filterValues={query.filterValues}
              onFilterChange={query.handleFilterChange}
              geojsonFile={query.geojsonFile}
              geojsonKey={query.geojsonResetKey}
              onGeojsonUpload={query.handleGeojsonUpload}
              onApplyFilters={query.handleApplyFilters}
              onNext={query.handleNext}
              pageSize={query.PAGE_SIZE}
              onExtractSpectra={() => {
                if (!window.confirm('Are you sure you want to run ISOFIT?')) return;
                isofit.handleRunIsoFit();
              }}
              extractLabel="Run ISOFIT"
              onDownloadTable={() => {}}
              loading={query.loading}
              nextDisabled={query.nextDisabled}
              extractDisabled={query.extractDisabled}
              downloadTableDisabled
            />

            {query.loading && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
                <CircularProgress />
              </Box>
            )}

            {query.error && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => query.setError(null)}>
                {query.error}
              </Alert>
            )}

            <IsoFitStatus
              parentJobId={isofit.isoFitJobId}
              isPolling={isofit.isIsoFitPolling}
              onStopPolling={() => isofit.setIsIsoFitPolling(false)}
            />

            <IsoFitHistory
              activeJobId={isofit.isoFitJobId}
              onMonitor={(jobId) => {
                isofit.setActiveJobId(jobId);
                isofit.setIsIsoFitPolling(true);
              }}
            />
          </Box>

          {/* ── Right — map (collapsed by default) + table ────────────── */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <MapView
              mapData={query.mapData}
              filterData={query.filterMapData}
              center={query.mapCenter}
              zoom={query.mapZoom}
              defaultCollapsed
              height={350}
            />
            <DataTable
              columns={query.tableColumns}
              data={query.tableData}
              summarizeValue={summarizeValue}
            />
          </Box>

        </Stack>
      </Container>
    </Box>
  );
}

export default IsoFitPage;
