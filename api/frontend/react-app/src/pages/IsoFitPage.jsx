import React from 'react';
import { Container, Box, CircularProgress, Alert, Stack } from '@mui/material';
import Navbar from '../components/Navbar';
import QueryFilterSection from '../components/QueryFilterSection';
import IsoFitStatus from '../components/IsoFitStatus';
import IsoFitHistory from '../components/IsoFitHistory';
import MapView from '../components/MapView';
import DataTable from '../components/DataTable';
import { summarizeValue } from '../utils/helpers';
import { useQueryPage } from '../hooks/useQueryPage';
import { useIsoFitJob } from '../hooks/useIsoFitJob';

function IsoFitPage() {
  const { view, query, viewOptions, currentViewConfig, handleViewChange, handleReset, hideExtract } = useQueryPage();

  const isofit = useIsoFitJob(
    query.getPixelRanges,
    query.setError,
    query.setExtractDisabled,
  );

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Navbar />
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>

        {/* ── Top — job monitoring + history full width ──────────────────── */}
        <Box sx={{ mb: 3 }}>
          <IsoFitStatus
            parentJobId={isofit.isoFitJobId}
            isPolling={isofit.isIsoFitPolling}
            onStopPolling={() => isofit.setIsIsoFitPolling(false)}
            onStartPolling={() => isofit.setIsIsoFitPolling(true)}
            onClose={() => { isofit.setIsIsoFitPolling(false); isofit.setActiveJobId(null); }}
          />
          <IsoFitHistory
            activeJobId={isofit.isoFitJobId}
            onMonitor={(jobId) => {
              isofit.setActiveJobId(jobId);
              isofit.setIsIsoFitPolling(false);
            }}
          />
        </Box>

        {/* ── Bottom — filters left, map + table right ────────────────────── */}
        <Stack direction={{ xs: 'column', lg: 'row' }} spacing={3} alignItems="flex-start">

          {/* Left — filters */}
          <Box sx={{ width: { xs: '100%', lg: 380 }, flexShrink: 0 }}>
            <QueryFilterSection
              query={query}
              currentViewConfig={currentViewConfig}
              view={view}
              viewOptions={viewOptions}
              onViewChange={handleViewChange}
              onReset={() => handleReset(isofit.reset)}
              onExtractSpectra={() => {
                if (!window.confirm('Are you sure you want to run ISOFIT?')) return;
                isofit.handleRunIsoFit();
              }}
              extractLabel="Run ISOFIT"
              onDownloadTable={() => {}}
              downloadTableDisabled
              hideExtract={hideExtract}
            />

            {query.loading && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                <CircularProgress />
              </Box>
            )}

            {query.error && (
              <Alert severity="error" sx={{ mt: 2 }} onClose={() => query.setError(null)}>
                {query.error}
              </Alert>
            )}
          </Box>

          {/* Right — map + table */}
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
              defaultCollapsed
            />
          </Box>

        </Stack>
      </Container>
    </Box>
  );
}

export default IsoFitPage;
