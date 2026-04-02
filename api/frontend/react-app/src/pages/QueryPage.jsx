import React from 'react';
import { Container, Box, CircularProgress, Alert } from '@mui/material';
import Navbar from '../components/Navbar';
import QueryFilterSection from '../components/QueryFilterSection';
import JobStatus from '../components/JobStatus';
import MapView from '../components/MapView';
import DataTable from '../components/DataTable';
import { summarizeValue, convertToCSV, parseFilters } from '../utils/helpers';
import { SELECT_CONFIGS } from '../viewConfig';
import { fetchParquet } from '../utils/api';
import { useQueryPage } from '../hooks/useQueryPage';
import { useSpectraExtraction } from '../hooks/useSpectraExtraction';

function QueryPage() {
  const { view, query, viewOptions, currentViewConfig, handleViewChange, handleReset, hideExtract } = useQueryPage();

  const spectra = useSpectraExtraction(
    query.getPixelRanges,
    query.setError,
    query.setExtractDisabled,
  );

  const handleDownloadTable = async () => {
    try {
      const filename = window.prompt('Enter file name:', 'table_data');
      if (!filename) return;
      const filters   = parseFilters(query.filterValues, query.geojsonContent);
      const result    = await fetchParquet(view, filters);
      const columns   = SELECT_CONFIGS[view];
      const geomIndex = columns.findIndex(c => c === 'geom' || c === 'geometry');

      if (geomIndex !== -1) {
        const propColumns = columns.filter((_, i) => i !== geomIndex);
        const features = result.data.map(row => {
          const geomVal  = row[geomIndex];
          const propVals = row.filter((_, i) => i !== geomIndex);
          const properties = Object.fromEntries(propColumns.map((col, i) => [col, propVals[i]]));
          let geometry = null;
          try { geometry = typeof geomVal === 'string' ? JSON.parse(geomVal) : geomVal; } catch {}
          return { type: 'Feature', geometry, properties };
        });
        const blob = new Blob(
          [JSON.stringify({ type: 'FeatureCollection', features }, null, 2)],
          { type: 'application/json' }
        );
        const url  = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href     = url;
        link.download = `${filename}.geojson`;
        document.body.appendChild(link);
        link.click();
        URL.revokeObjectURL(url);
        document.body.removeChild(link);
      } else {
        const rows = convertToCSV(result.data, columns);
        const link = document.createElement('a');
        link.setAttribute('href', encodeURI('data:text/csv;charset=utf-8,\uFEFF' + rows));
        link.setAttribute('download', `${filename}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    } catch (err) {
      query.setError(err.message);
    }
  };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Navbar />
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <QueryFilterSection
          query={query}
          currentViewConfig={currentViewConfig}
          view={view}
          viewOptions={viewOptions}
          onViewChange={handleViewChange}
          onReset={() => handleReset(spectra.reset)}
          onExtractSpectra={spectra.handleExtractSpectra}
          onDownloadTable={handleDownloadTable}
          hideExtract={hideExtract}
        />

        <JobStatus
          jobsBySensor={spectra.jobsBySensor ?? {}}
          sensorStatuses={spectra.sensorStatuses ?? {}}
        />

        {query.loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
            <CircularProgress />
          </Box>
        )}

        {query.error && (
          <Alert severity="error" sx={{ mb: 3 }} onClose={() => query.setError(null)}>
            {query.error}
          </Alert>
        )}

        {Object.entries(spectra.sensorStatuses ?? {}).some(([, s]) => s.error) && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {Object.entries(spectra.sensorStatuses)
              .filter(([, s]) => s.error)
              .map(([key, s]) => `${key}: ${s.error}`)
              .join(' | ')}
          </Alert>
        )}

        <MapView mapData={query.mapData} filterData={query.filterMapData} center={query.mapCenter} zoom={query.mapZoom} />
        <DataTable columns={query.tableColumns} data={query.tableData} summarizeValue={summarizeValue} />
      </Container>
    </Box>
  );
}

export default QueryPage;
