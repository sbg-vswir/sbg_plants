import React, { useState, useMemo } from 'react';
import { Container, Box, CircularProgress, Alert } from '@mui/material';
import Navbar from './components/Navbar';
import FilterSection from './components/FilterSection';
import JobStatus from './components/JobStatus';
import MapView from './components/MapView';
import DataTable from './components/DataTable';
import { VIEW_CONFIGS, SELECT_CONFIGS } from './viewConfig';
import { fetchParquet, extractSpectra } from './utils/api';
import { 
  parseFilters, 
  summarizeValue, 
  convertToCSV, 
  extractPixelIds, 
  toRanges 
} from './utils/helpers';
import { useJobPolling } from './hooks/useJobPolling';

const PAGE_SIZE = 4000;

function App() {
  // State
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
  const [jobId, setJobId] = useState(null);
  const [isPolling, setIsPolling] = useState(false);
  const [nextDisabled, setNextDisabled] = useState(true);
  const [extractDisabled, setExtractDisabled] = useState(true);
  const [downloadTableDisabled, setDownloadTableDisabled] = useState(true);
  
  // Custom hook for job polling
  const { rowsProcessed, downloadUrl, pollingError, status} = useJobPolling(jobId, isPolling);

  // Get current view config
  const currentViewConfig = VIEW_CONFIGS[view] || { filters: [] };
  const views = Object.keys(VIEW_CONFIGS);

  // Compute table columns from config
  const tableColumns = useMemo(() => {
    if (tableData.length === 0) return [];
    
    // Get all keys from the first row, filter out geom
    let allKeys = Object.keys(tableData[0]).filter(key => key !== 'geom');
    
    // Move id to the front if it exists
    const idIndex = allKeys.indexOf('id');
    if (idIndex > -1) {
      allKeys.splice(idIndex, 1);
      allKeys.unshift('id');
    }
    
    // Transform to objects with labels
    const cols = allKeys.map(key => ({
      key: key,
      label: key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
    }));

    return cols;
  }, [tableData]);

  // Handlers
  const handleViewChange = (e) => {
    const newView = e.target.value;
    setView(newView);
    handleReset(false);
  };

  const handleFilterChange = (filterId, value) => {
    setFilterValues(prev => ({
      ...prev,
      [filterId]: value
    }));
  };

  const handleGeojsonUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setGeojsonFile(file);
      const reader = new FileReader();
      reader.onload = (event) => {
        setGeojsonContent(event.target.result);
      };
      reader.readAsText(file);
    }
  };

  const updateTableAndMap = (result, currentOffset, resetView = true) => {
    const { data, geojson } = result;
    
    // Get column names from SELECT_CONFIGS
    const columnNames = SELECT_CONFIGS[view] || [];
    
    // Process table data - map numeric indices to column names
    const tableRows = data.map((row, idx) => {
      const namedRow = { id: currentOffset + idx };
      
      // Map each column name to its corresponding index
      columnNames.forEach((colName, colIndex) => {
        if (colName !== 'geom') {
          namedRow[colName] = row[colIndex];
        }
      });
      
      // Store geom separately if it exists
      const geomIndex = columnNames.indexOf('geom');
      if (geomIndex > -1 && row[geomIndex]) {
        namedRow.geom = row[geomIndex];
      }
      
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
    
    // Update map
    if (geojson) {
      setMapData(geojson);
      if (resetView) {
        setMapCenter([0, 0]);
        setMapZoom(2);
      }
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

  const handleExtractSpectra = async () => {
    if (!tableData.length) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const filters = parseFilters(filterValues, geojsonContent);
      const result = await fetchParquet(view, filters);
      
      const pixelIds = extractPixelIds(result.data, SELECT_CONFIGS[view]);
      
      if (pixelIds.length === 0) {
        setError('No pixel IDs found');
        setLoading(false);
        return;
      }
      
      const pixelRanges = toRanges(pixelIds);
      
      const newJobId = await extractSpectra(pixelRanges);
      setJobId(newJobId);
      setIsPolling(true);
      setExtractDisabled(true);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadTable = async () => {
    try {
      const filters = parseFilters(filterValues, geojsonContent);
      const result = await fetchParquet(view, filters);
      
      const csv = convertToCSV(result.data);
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'table_data.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleReset = (resetView = true) => {
    if (resetView) {
      setView('plot_pixels_mv');
    }
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
    setJobId(null);
    setIsPolling(false);
    setError(null);
  };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Navbar 
        view={view}
        views={views}
        onViewChange={handleViewChange}
        onReset={handleReset}
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
          onExtractSpectra={handleExtractSpectra}
          onDownloadTable={handleDownloadTable}
          loading={loading}
          nextDisabled={nextDisabled}
          extractDisabled={extractDisabled}
          downloadTableDisabled={downloadTableDisabled}
        />

       <JobStatus
        jobId={jobId}
        rowsProcessed={rowsProcessed}
        downloadUrl={downloadUrl}
        status={status}
      />

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

        {pollingError && (
          <Alert severity="error" sx={{ mb: 3 }}>
            Polling error: {pollingError}
          </Alert>
        )}

        <MapView 
          mapData={mapData}
          center={mapCenter}
          zoom={mapZoom}
        />

        <DataTable
          columns={tableColumns}
          data={tableData}
          summarizeValue={summarizeValue}
        />
      </Container>
    </Box>
  );
}

export default App;