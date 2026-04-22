import { useState, useMemo } from 'react';
import { fetchParquet } from '../utils/api';
import { parseFilters, summarizeValue, extractPixelIds, toRanges } from '../utils/helpers';
import { SELECT_CONFIGS } from '../viewConfig';

const PAGE_SIZE = 4000;

export function useDataQuery(view) {
  const [filterValues, setFilterValues]   = useState({});
  const [geojsonFile, setGeojsonFile]       = useState(null);
  const [geojsonContent, setGeojsonContent] = useState(null);
  const [geojsonResetKey, setGeojsonResetKey] = useState(0);
  const [tableData, setTableData]         = useState([]);
  const [mapData, setMapData]             = useState(null);
  const [filterMapData, setFilterMapData] = useState(null);
  const [mapCenter, setMapCenter]         = useState([0, 0]);
  const [mapZoom, setMapZoom]             = useState(2);
  const [offset, setOffset]               = useState(0);
  const [loading, setLoading]             = useState(false);
  const [error, setError]                 = useState(null);

  // Button disabled states
  const [nextDisabled, setNextDisabled]               = useState(true);
  const [extractDisabled, setExtractDisabled]         = useState(true);
  const [downloadTableDisabled, setDownloadTableDisabled] = useState(true);

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
      label: key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
    }));
  }, [tableData]);

  const _applyResult = (result, currentOffset, resetView = true) => {
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

    const hasRows = tableRows.length > 0;
    setNextDisabled(!hasRows);
    setExtractDisabled(!hasRows || view === 'trait_view');
    setDownloadTableDisabled(!hasRows);

    if (geojson) {
      setMapData(geojson);
      if (resetView) { setMapCenter([0, 0]); setMapZoom(2); }
    }
  };

  const handleFilterChange = (filterId, value) => {
    setFilterValues(prev => ({ ...prev, [filterId]: value }));
  };

  const handleGeojsonUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setGeojsonFile(file);
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target.result;
      setGeojsonContent(text);
      try {
        const parsed = JSON.parse(text);
        setFilterMapData(parsed);
      } catch {
        // invalid GeoJSON — store text for filter query, just don't render
      }
    };
    reader.readAsText(file);
  };

  const handleApplyFilters = async () => {
    setLoading(true);
    setError(null);
    setOffset(0);
    try {
      const filters = parseFilters(filterValues, geojsonContent);
      const result = await fetchParquet(view, filters, PAGE_SIZE, 0);
      _applyResult(result, 0, true);
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
      _applyResult(result, newOffset, false);
      setOffset(newOffset);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getPixelRanges = async () => {
    const filters = parseFilters(filterValues, geojsonContent);
    const result = await fetchParquet(view, filters);
    const pixelIds = extractPixelIds(result.data, SELECT_CONFIGS[view]);
    if (Object.keys(pixelIds).length === 0) throw new Error('No pixel IDs found');
    return Object.fromEntries(
      Object.entries(pixelIds).map(([key, ids]) => [key, toRanges(ids)])
    );
  };

  const reset = (resetView = true) => {
    setFilterValues({});
    setGeojsonFile(null);
    setGeojsonContent(null);
    setGeojsonResetKey(k => k + 1);
    setTableData([]);
    setMapData(null);
    setFilterMapData(null);
    setMapCenter([0, 0]);
    setMapZoom(2);
    setOffset(0);
    setNextDisabled(true);
    setExtractDisabled(true);
    setDownloadTableDisabled(true);
    setError(null);
  };

  return {
    // state
    filterValues,
    geojsonFile,
    geojsonResetKey,
    tableData,
    tableColumns,
    mapData,
    filterMapData,
    mapCenter,
    mapZoom,
    loading,
    error,
    setError,
    nextDisabled,
    extractDisabled,
    setExtractDisabled,
    downloadTableDisabled,
    // derived
    PAGE_SIZE,
    geojsonContent,
    // handlers
    handleFilterChange,
    handleGeojsonUpload,
    handleApplyFilters,
    handleNext,
    getPixelRanges,
    reset,
  };
}
