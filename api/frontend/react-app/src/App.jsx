import React, { useState, useEffect, useMemo } from 'react';
import { Container, Box, CircularProgress, Alert, Button } from '@mui/material';
import Navbar from './components/Navbar';
import FilterSection from './components/FilterSection';
import JobStatus from './components/JobStatus';
import IsoFitStatus from './components/IsoFitStatus';
// import IsoFitDashboard from './components/IsoFitDashboard';
import MapView from './components/MapView';
import DataTable from './components/DataTable';
import { VIEW_CONFIGS, SELECT_CONFIGS } from './viewConfig';
import { fetchParquet, extractSpectra, submitIsofitRun } from './utils/api';
import { parseFilters, summarizeValue, convertToCSV, extractPixelIds, toRanges } from './utils/helpers';
import { useJobPolling } from './hooks/useJobPolling';
import LoginButton from './components/LoginButton';
import { getAuthCode, getStoredTokens, storeTokens, exchangeCodeForTokens, isTokenExpired } from './utils/auth';
import { Campaign } from '@mui/icons-material';

const PAGE_SIZE = 4000;

function App() {
  const [authState, setAuthState] = useState('loading');
  const [mode, setMode] = useState('spectra'); // 'spectra' | 'isofit'
  const [view, setView] = useState('plot_pixels_mv');
  const [filterValues, setFilterValues] = useState({});
  const [geojsonFile, setGeojsonFile] = useState(null);
  const [geojsonContent, setGeojsonContent] = useState(null);
  const [tableData, setTableData] = useState([]);
  const [mapData, setMapData] = useState(null);
  const [mapCenter, setMapCenter] = useState([0, 0]);
  const [mapZoom, setMapZoom] = useState(2);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Spectra job state
  const [jobsBySensor, setJobsBySensor] = useState({});
  const [isPolling, setIsPolling] = useState(false);
  const { sensorStatuses } = useJobPolling(jobsBySensor, isPolling);


  // IsoFit job state
  const [isoFitJobId, setIsoFitJobId] = useState(null);
  const [isIsoFitPolling, setIsIsoFitPolling] = useState(false);

  const [nextDisabled, setNextDisabled] = useState(true);
  const [extractDisabled, setExtractDisabled] = useState(true);
  const [downloadTableDisabled, setDownloadTableDisabled] = useState(true);

  // const { rowsProcessed, downloadUrl, pollingError, status } = useJobPolling(jobId, isPolling);
  const currentViewConfig = VIEW_CONFIGS[view] || { filters: [] };
  const views = Object.keys(VIEW_CONFIGS);

  const [isoFitJobHistory, setIsoFitJobHistory] = useState(() => {
    // load from localStorage on first render
    try {
      const stored = localStorage.getItem('isoFitJobHistory');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const saveIsoFitHistory = (history) => {
    setIsoFitJobHistory(history);
    localStorage.setItem('isoFitJobHistory', JSON.stringify(history));
  };

  const tableColumns = useMemo(() => {
    if (tableData.length === 0) return [];
    let allKeys = Object.keys(tableData[0]).filter(key => key !== 'geom');
    const idIndex = allKeys.indexOf('id');
    if (idIndex > -1) {
      allKeys.splice(idIndex, 1);
      allKeys.unshift('id');
    }
    return allKeys.map(key => ({
      key,
      label: key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
    }));
  }, [tableData]);

  useEffect(() => {
    const tokens = getStoredTokens();
    const code = getAuthCode();
    if (tokens && !isTokenExpired(tokens)) {
      setAuthState('loggedIn');
    } else if (code) {
      window.history.replaceState({}, document.title, '/');
      exchangeCodeForTokens(code)
        .then((tokens) => { storeTokens(tokens); setAuthState('loggedIn'); })
        .catch(() => setAuthState('loggedOut'));
    } else {
      setAuthState('loggedOut');
    }
  }, []);

  const handleViewChange = (e) => {
    setView(e.target.value);
    handleReset(false);
  };

  const handleFilterChange = (filterId, value) => {
    setFilterValues(prev => ({ ...prev, [filterId]: value }));
  };

  const handleGeojsonUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setGeojsonFile(file);
      const reader = new FileReader();
      reader.onload = (event) => setGeojsonContent(event.target.result);
      reader.readAsText(file);
    }
  };

  const updateTableAndMap = (result, currentOffset, resetView = true) => {
    const { data, geojson } = result;
    const columnNames = SELECT_CONFIGS[view] || [];
    const tableRows = data.map((row, idx) => {
      const namedRow = { id: currentOffset + idx };
      columnNames.forEach((colName, colIndex) => {
        if (colName !== 'geom') namedRow[colName] = row[colIndex];
      });
      const geomIndex = columnNames.indexOf('geom');
      if (geomIndex > -1 && row[geomIndex]) namedRow.geom = row[geomIndex];
      return namedRow;
    });
    setTableData(tableRows);
    if (tableRows.length > 0) {
      setNextDisabled(false);
      setExtractDisabled(view === 'leaf_traits_view');
      setDownloadTableDisabled(false);
    } else {
      setNextDisabled(true);
      setExtractDisabled(true);
      setDownloadTableDisabled(true);
    }
    if (geojson) {
      setMapData(geojson);
      if (resetView) { setMapCenter([0, 0]); setMapZoom(2); }
    }
  };

  const handleApplyFilters = async () => {
    setLoading(true);
    setError(null);
    setOffset(0);
    try {
      const filters = parseFilters(filterValues, geojsonContent);
      const result = await fetchParquet(view, filters, PAGE_SIZE, 0);
      updateTableAndMap(result, 0, true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleNext = async () => {
    setLoading(true);
    setError(null);
    const newOffset = offset + PAGE_SIZE;
    try {
      const filters = parseFilters(filterValues, geojsonContent);
      const result = await fetchParquet(view, filters, PAGE_SIZE, newOffset);
      updateTableAndMap(result, newOffset, false);
      setOffset(newOffset);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Shared pixel ID extraction
  const getPixelRanges = async () => {
    const filters = parseFilters(filterValues, geojsonContent);
    const result = await fetchParquet(view, filters);
    const pixelIds = extractPixelIds(result.data, SELECT_CONFIGS[view]);
    if (pixelIds.length === 0) throw new Error('No pixel IDs found');

    const pixelRanges = Object.fromEntries(
      Object.entries(pixelIds).map(([key, ids]) => [key, toRanges(ids)])
    );

    return pixelRanges;
  };

  const handleExtractSpectra = async () => {
    if (!tableData.length) return;
    setLoading(true);
    setError(null);
    try {
      const pixelRangesBySensor = await getPixelRanges(); // now returns the map
      const jobs = await extractSpectra(pixelRangesBySensor);
      setJobsBySensor(jobs);
      setIsPolling(true);
      setExtractDisabled(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRunIsoFit = async () => {
    if (!tableData.length) return;
    setLoading(true);
    setError(null);
    try {
      const pixelRanges = await getPixelRanges();
      const payload = { 
        pixel_ranges: pixelRanges
      };
    
      const response = await submitIsofitRun(payload);
      const id = response.data.parent_job_id || response.data.job_id;
      const createdAt = response.data.created_at
      setIsoFitJobId(id);
      setIsIsoFitPolling(true);
      
      // update history — do NOT overwrite created_at if already exists
      const newHistory = [...isoFitJobHistory];
      if (!newHistory.find(j => j.jobId === id)) {
        newHistory.push({ jobId: id, createdAt });
        saveIsoFitHistory(newHistory);
      }

      setExtractDisabled(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // --- restore last active job on mount ---
  useEffect(() => {
    if (!isoFitJobId && isoFitJobHistory.length > 0) {
      // pick the most recent job
      const lastJob = isoFitJobHistory[isoFitJobHistory.length - 1];
      setIsoFitJobId(lastJob.jobId);
      setIsIsoFitPolling(true); // optionally start polling automatically
    }
  }, []);

  const handleDownloadTable = async () => {
    try {
      const filename = window.prompt('Enter file name:', 'table_data');
      if (!filename) return;
      const filters = parseFilters(filterValues, geojsonContent);
      const result = await fetchParquet(view, filters);
      const columns = SELECT_CONFIGS[view];
      const geomIndex = columns.findIndex(col => col.toLowerCase() === 'geometry' || col.toLowerCase() === 'geom');
      const hasGeometry = geomIndex !== -1;
      if (hasGeometry) {
        const propertyColumns = columns.filter((_, i) => i !== geomIndex);
        const features = result.data.map(row => {
          const geometryValue = row[geomIndex];
          const propValues = row.filter((_, i) => i !== geomIndex);
          const properties = Object.fromEntries(propertyColumns.map((col, i) => [col, propValues[i]]));
          let geometry = null;
          try { geometry = typeof geometryValue === 'string' ? JSON.parse(geometryValue) : geometryValue; } catch { }
          return { type: 'Feature', geometry, properties };
        });
        const geojson = JSON.stringify({ type: 'FeatureCollection', features }, null, 2);
        const blob = new Blob([geojson], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${filename}.geojson`;
        document.body.appendChild(link);
        link.click();
        URL.revokeObjectURL(url);
        document.body.removeChild(link);
      } else {
        const cleanColumns = columns.map(col => col.label);
        const rows = convertToCSV(result.data, cleanColumns);
        const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + rows;
        const link = document.createElement('a');
        link.setAttribute('href', encodeURI(csvContent));
        link.setAttribute('download', `${filename}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const handleReset = (resetView = true) => {
    if (resetView) setView('plot_pixels_mv');
    setFilterValues({});
    setGeojsonFile(null);
    setGeojsonContent(null);
    setTableData([]);
    setMapData(null);
    setMapCenter([0, 0]);
    setMapZoom(2);
    setOffset(0);
    setNextDisabled(true);
    setExtractDisabled(true);
    setDownloadTableDisabled(true);
    setJobsBySensor({});
    // setJobId(null);
    setIsPolling(false);
    setIsoFitJobId(null);
    setIsIsoFitPolling(false);
    setError(null);
  };

  if (authState === 'loading') return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
      <CircularProgress />
    </Box>
  );

  if (authState === 'loggedOut') return <LoginButton />;

  // IsoFit dashboard mode — full standalone page for monitoring existing jobs
  if (mode === 'isofit_dashboard') return (
    <Box sx={{ flexGrow: 1 }}>
      <Navbar
        view={view}
        views={views}
        onViewChange={handleViewChange}
        onReset={handleReset}
        showControls={false}
        onIsoFitClick={() => setMode('isofit_dashboard')}
        onHomeClick={() => setMode('spectra')}
      />
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <Button variant="text" onClick={() => setMode('spectra')} sx={{ mb: 2 }}>
          ← Back
        </Button>
        {/* <IsoFitDashboard initialJobId={isoFitJobId} onJobStarted={setIsoFitJobId} /> */}
      </Container>
    </Box>
  );

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Navbar
        view={view}
        views={views}
        onViewChange={handleViewChange}
        onReset={handleReset}
        onIsoFitClick={() => setMode(prev => prev === 'isofit' ? 'spectra' : 'isofit')}
        isIsoFitMode={mode === 'isofit'}
      />
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <FilterSection
          filters={currentViewConfig.filters}
          filterValues={filterValues}
          onFilterChange={handleFilterChange}
          geojsonFile={geojsonFile}
          onGeojsonUpload={handleGeojsonUpload}
          onApplyFilters={handleApplyFilters}
          onNext={handleNext}
          onExtractSpectra={mode === 'isofit' ? handleRunIsoFit : handleExtractSpectra}
          isIsoFitMode={mode === 'isofit'}
          onDownloadTable={handleDownloadTable}
          loading={loading}
          nextDisabled={nextDisabled}
          extractDisabled={extractDisabled}
          downloadTableDisabled={downloadTableDisabled}
        />

        {/* Job status — swaps based on mode */}
        {mode === 'isofit' ? (
          <IsoFitStatus
            parentJobId={isoFitJobId}
            isPolling={isIsoFitPolling}
            onStopPolling={() => setIsIsoFitPolling(false)}
          />
        ) : (
          <JobStatus
            jobsBySensor={jobsBySensor ?? {}}
            sensorStatuses={sensorStatuses ?? {}}
          />
        )}

        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
            <CircularProgress />
          </Box>
        )}
        {error && (
          <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        {mode === 'spectra' && Object.entries(sensorStatuses ?? {}).some(([, s]) => s.error) && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {Object.entries(sensorStatuses)
              .filter(([, s]) => s.error)
              .map(([key, s]) => `${key}: ${s.error}`)
              .join(' | ')}
          </Alert>
        )}

        <MapView mapData={mapData} center={mapCenter} zoom={mapZoom} />
        <DataTable columns={tableColumns} data={tableData} summarizeValue={summarizeValue} />
      </Container>
    </Box>
  );
}

export default App;