import { useState, useCallback, useRef } from 'react';
import { fetchLinkedQuery, fetchLinkedQueryAll } from '../utils/api';
import { toRanges } from '../utils/helpers';

/**
 * All state and logic for LinkedQueryPage.
 */
export function useLinkedQuery() {
  // -------------------------------------------------------------------------
  // Filter state
  // -------------------------------------------------------------------------
  const [campaignName, setCampaignName]     = useState('');
  const [geojsonContent, setGeojsonContent] = useState(null);
  const [geojsonIsDrawn, setGeojsonIsDrawn] = useState(false);
  const [traitFilters, setTraitFilters]     = useState({
    trait:                 [],
    taxa:                  [],
    veg_or_cover_type:     [],
    phenophase:            [],
    plant_status:          [],
    canopy_position:       [],
    plot_veg_type:         [],
    subplot_cover_method:  [],
    sample_fc_class:       [],
    handling:              [],
    method:                [],
    sample_name:           '',
    plot_name:             '',
    collection_date_start: '',
    collection_date_end:   '',
  });
  const [granuleFilters, setGranuleFilters] = useState({
    sensor_name:            [],
    cloudy_conditions:      [],
    cloud_type:             [],
    acquisition_date_start: '',
    acquisition_date_end:   '',
  });

  // -------------------------------------------------------------------------
  // Pagination state
  // -------------------------------------------------------------------------
  const [offset, setOffset] = useState(0);
  const [limit]             = useState(100);

  // -------------------------------------------------------------------------
  // Response state
  // -------------------------------------------------------------------------
  const [plots,    setPlots]    = useState(null);
  const [hasQueried, setHasQueried] = useState(false);
  const [traits,   setTraits]   = useState([]);
  const [granules, setGranules] = useState([]);
  const [totalPlots,    setTotalPlots]    = useState(0);
  const [totalTraits,   setTotalTraits]   = useState(0);
  const [totalGranules, setTotalGranules] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [displayedOffset, setDisplayedOffset] = useState(0);

  const lastPayloadRef    = useRef(null);
  const allGranulesCache  = useRef(null);
  const allTraitsCache    = useRef(null);

  // -------------------------------------------------------------------------
  // Pixel count state
  // -------------------------------------------------------------------------
  const [totalPixelCount, setTotalPixelCount] = useState(null);  // null = not yet fetched
  const [pixelCountLoading, setPixelCountLoading] = useState(false);
  const [totalCsvRows, setTotalCsvRows] = useState(null);  // null = not yet computed

  // -------------------------------------------------------------------------
  // Selected plot state
  // -------------------------------------------------------------------------
  const [selectedPlotId, setSelectedPlotId] = useState(null);

  const selectedTraits = selectedPlotId
    ? traits.filter(t => t.plot_id === selectedPlotId)
    : [];

  const selectedGranules = selectedPlotId
    ? granules.filter(g => Array.isArray(g.plot_ids) && g.plot_ids.includes(selectedPlotId))
    : [];

  // -------------------------------------------------------------------------
  // Build query payload
  // -------------------------------------------------------------------------
  const _buildPayload = useCallback((overrideOffset = offset) => {
    const payload = { limit, offset: overrideOffset };

    if (campaignName) payload.campaign_name = campaignName;
    if (geojsonContent) payload.geojson = geojsonContent;

    const tf = {};
    if (traitFilters.trait?.length)                tf.trait                = traitFilters.trait;
    if (traitFilters.taxa?.length)                 tf.taxa                 = traitFilters.taxa;
    if (traitFilters.veg_or_cover_type?.length)    tf.veg_or_cover_type    = traitFilters.veg_or_cover_type;
    if (traitFilters.phenophase?.length)           tf.phenophase           = traitFilters.phenophase;
    if (traitFilters.plant_status?.length)         tf.plant_status         = traitFilters.plant_status;
    if (traitFilters.canopy_position?.length)      tf.canopy_position      = traitFilters.canopy_position;
    if (traitFilters.plot_veg_type?.length)        tf.plot_veg_type        = traitFilters.plot_veg_type;
    if (traitFilters.subplot_cover_method?.length) tf.subplot_cover_method = traitFilters.subplot_cover_method;
    if (traitFilters.sample_fc_class?.length)      tf.sample_fc_class      = traitFilters.sample_fc_class;
    if (traitFilters.handling?.length)             tf.handling             = traitFilters.handling;
    if (traitFilters.method?.length)               tf.method               = traitFilters.method;
    if (traitFilters.sample_name)                  tf.sample_name          = traitFilters.sample_name;
    if (traitFilters.plot_name)                    tf.plot_name            = traitFilters.plot_name;
    if (traitFilters.collection_date_start)        tf.collection_date_start = traitFilters.collection_date_start;
    if (traitFilters.collection_date_end)          tf.collection_date_end   = traitFilters.collection_date_end;
    if (Object.keys(tf).length)                    payload.trait_filters   = tf;

    const gf = {};
    if (granuleFilters.sensor_name?.length)         gf.sensor_name            = granuleFilters.sensor_name;
    if (granuleFilters.cloudy_conditions?.length)   gf.cloudy_conditions      = granuleFilters.cloudy_conditions;
    if (granuleFilters.cloud_type?.length)          gf.cloud_type             = granuleFilters.cloud_type;
    if (granuleFilters.acquisition_date_start)       gf.acquisition_date_start = granuleFilters.acquisition_date_start;
    if (granuleFilters.acquisition_date_end)         gf.acquisition_date_end   = granuleFilters.acquisition_date_end;
    if (Object.keys(gf).length)                      payload.granule_filters   = gf;

    return payload;
  }, [campaignName, geojsonContent, traitFilters, granuleFilters, limit, offset]);

  // -------------------------------------------------------------------------
  // Execute query
  // -------------------------------------------------------------------------
  const _runQuery = useCallback(async (payload) => {
    setLoading(true);
    setError(null);
    setTotalPixelCount(null);
    setPixelCountLoading(true);
    setTotalCsvRows(null);
    allGranulesCache.current = null;
    allTraitsCache.current = null;
    console.log('[useLinkedQuery] _runQuery called with payload:', payload);
    try {
      const data = await fetchLinkedQuery({ ...payload, format: 'geojson' });
      console.log('[useLinkedQuery] response keys:', Object.keys(data), 'total_plots:', data.total_plots);
      const plotsGeojson = data.plots_geojson ?? (data.plots?.type === 'FeatureCollection' ? data.plots : null);
      setPlots(plotsGeojson);
      setHasQueried(true);
      setTraits(data.traits    ?? []);
      setGranules(data.granules ?? []);
      setTotalPlots(data.total_plots    ?? 0);
      setTotalTraits(data.total_traits   ?? 0);
      setTotalGranules(data.total_granules ?? 0);
      setTruncated(data.truncated ?? false);
      setDisplayedOffset(payload.offset ?? 0);
      lastPayloadRef.current = payload;

      // Background fetch — get all granules to compute total pixel count and
      // cache for getPixelRanges so it doesn't need to fetch again.
      const basePayload = { ...payload };
      delete basePayload.offset;
      delete basePayload.limit;
      fetchLinkedQueryAll({ ...basePayload, format: 'json' })
        .then(allData => {
          const allG = allData.granules ?? [];
          const allT = allData.traits   ?? [];
          allGranulesCache.current = allG;
          allTraitsCache.current   = allT;

          // Total pixel count
          const total = allG.reduce((sum, g) => sum + (Array.isArray(g.pixel_ids) ? g.pixel_ids.length : 0), 0);
          setTotalPixelCount(total);
          setPixelCountLoading(false);

          // Total CSV rows — one row per trait × overlapping granules (min 1)
          const plotGranules = {};
          for (const g of allG) {
            for (const pid of (g.plot_ids ?? [])) {
              if (!plotGranules[pid]) plotGranules[pid] = [];
              plotGranules[pid].push(g);
            }
          }
          const csvRows = allT.reduce((sum, t) => {
            const overlapping = plotGranules[t.plot_id] ?? [];
            return sum + Math.max(1, overlapping.length);
          }, 0);
          setTotalCsvRows(csvRows);
        })
        .catch(() => {
          setPixelCountLoading(false);
        });
    } catch (err) {
      console.error('[useLinkedQuery] error:', err);
      setError(err.response?.data?.error ?? err.message ?? 'Query failed');
      setPixelCountLoading(false);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleReset = useCallback(() => {
    // Filters
    setCampaignName('');
    setGeojsonContent(null);
    setGeojsonIsDrawn(false);
    setTraitFilters({
      trait: [], taxa: [], veg_or_cover_type: [], phenophase: [],
      plant_status: [], canopy_position: [], plot_veg_type: [],
      subplot_cover_method: [], sample_fc_class: [], handling: [],
      method: [], sample_name: '', plot_name: '',
      collection_date_start: '', collection_date_end: '',
    });
    setGranuleFilters({
      sensor_name: [], cloudy_conditions: [], cloud_type: [],
      acquisition_date_start: '', acquisition_date_end: '',
    });
    // Results
    setPlots(null);
    setHasQueried(false);
    setTraits([]);
    setGranules([]);
    setTotalPlots(0);
    setTotalTraits(0);
    setTotalGranules(0);
    setTruncated(false);
    setOffset(0);
    setDisplayedOffset(0);
    setSelectedPlotId(null);
    setError(null);
    setTotalPixelCount(null);
    setPixelCountLoading(false);
    setTotalCsvRows(null);
    lastPayloadRef.current = null;
    allGranulesCache.current = null;
    allTraitsCache.current = null;
  }, []);

  const handleApply = useCallback(() => {
    console.log('[useLinkedQuery] handleApply called');
    const payload = _buildPayload(0);
    console.log('[useLinkedQuery] payload built:', payload);
    setOffset(0);
    setSelectedPlotId(null);
    _runQuery(payload);
  }, [_buildPayload, _runQuery]);

  const handleNext = useCallback(() => {
    const newOffset = offset + limit;
    setOffset(newOffset);
    setSelectedPlotId(null);
    _runQuery(_buildPayload(newOffset));
  }, [offset, limit, _buildPayload, _runQuery]);

  const handlePrev = useCallback(() => {
    const newOffset = Math.max(0, offset - limit);
    setOffset(newOffset);
    setSelectedPlotId(null);
    _runQuery(_buildPayload(newOffset));
  }, [offset, limit, _buildPayload, _runQuery]);

  // -------------------------------------------------------------------------
  // getPixelRanges — fetches ALL matched granules (not just current page)
  // then computes pixel ranges for spectra extraction.
  // -------------------------------------------------------------------------
  const getPixelRanges = useCallback(async () => {
    const payload = lastPayloadRef.current;
    if (!payload) return {};

    // Use cached granules from background fetch if available — avoids a second call.
    let allGranules = allGranulesCache.current;
    if (!allGranules) {
      const raw = typeof payload === 'string' ? payload : JSON.stringify(payload);
      const sanitized = raw.replace(/:\s*NaN\b/g, ': null');
      const basePayload = JSON.parse(sanitized);
      const data = await fetchLinkedQueryAll({ ...basePayload, format: 'json' });
      allGranules = data.granules ?? [];
      allGranulesCache.current = allGranules;
    }

    const grouped = {};
    for (const g of allGranules) {
      const key = `${g.campaign_name}|${g.sensor_name}`;
      if (!grouped[key]) grouped[key] = [];
      if (Array.isArray(g.pixel_ids)) grouped[key].push(...g.pixel_ids);
    }
    const result = {};
    for (const [key, ids] of Object.entries(grouped)) {
      const sorted = [...new Set(ids)].sort((a, b) => a - b);
      result[key] = toRanges(sorted);
    }
    return result;
  }, []);

  // -------------------------------------------------------------------------
  // getMergedDownloadData — one row per trait measurement, granule columns
  // joined alongside. pixel_ids kept as a semicolon-separated string.
  // Async — fetches ALL pages. Uses cache populated by background fetch.
  // -------------------------------------------------------------------------
  const getMergedDownloadData = useCallback(async () => {
    const payload = lastPayloadRef.current;
    if (!payload) return [];

    // Ensure both caches are warm
    let allG = allGranulesCache.current;
    let allT = allTraitsCache.current;
    if (!allG || !allT) {
      const raw = typeof payload === 'string' ? payload : JSON.stringify(payload);
      const sanitized = raw.replace(/:\s*NaN\b/g, ': null');
      const basePayload = JSON.parse(sanitized);
      delete basePayload.offset;
      delete basePayload.limit;
      const data = await fetchLinkedQueryAll({ ...basePayload, format: 'json' });
      allG = data.granules ?? [];
      allT = data.traits   ?? [];
      allGranulesCache.current = allG;
      allTraitsCache.current   = allT;
    }

    // Build a lookup: plot_id → list of granules that overlap it
    const plotGranules = {};
    for (const g of allG) {
      for (const pid of (g.plot_ids ?? [])) {
        if (!plotGranules[pid]) plotGranules[pid] = [];
        plotGranules[pid].push(g);
      }
    }

    // One row per trait measurement; for each trait row join every overlapping granule
    return allT.flatMap(t => {
      const overlapping = plotGranules[t.plot_id] ?? [];
      if (overlapping.length === 0) {
        return [{ ...t }];
      }
      return overlapping.map(g => ({
        ...t,
        granule_id:             g.granule_id,
        campaign_name:          g.campaign_name,
        sensor_name:            g.sensor_name,
        acquisition_date:       g.acquisition_date,
        acquisition_start_time: g.acquisition_start_time,
        cloudy_conditions:      g.cloudy_conditions,
        cloud_type:             g.cloud_type,
        pixel_ids:              Array.isArray(g.pixel_ids) ? g.pixel_ids.join(';') : '',
        pixel_count:            Array.isArray(g.pixel_ids) ? g.pixel_ids.length : 0,
      }));
    });
  }, []);

  // -------------------------------------------------------------------------
  // Map data
  // -------------------------------------------------------------------------
  const mapData = plots?.type === 'FeatureCollection' ? plots : null;

  const filterMapData = geojsonContent && !geojsonIsDrawn
    ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: geojsonContent, properties: {} }] }
    : null;

  // Page-level pixel count — sum of pixel_ids across granules on the current page.
  const pagePixelCount = granules.reduce(
    (sum, g) => sum + (Array.isArray(g.pixel_ids) ? g.pixel_ids.length : 0), 0
  );

  return {
    // Filter state
    campaignName, setCampaignName,
    geojsonContent, setGeojsonContent, geojsonIsDrawn,
    setDrawnGeojson:    (geom) => { setGeojsonContent(geom); setGeojsonIsDrawn(geom != null); },
    setUploadedGeojson: (geom) => { setGeojsonContent(geom); setGeojsonIsDrawn(false); },
    traitFilters, setTraitFilters,
    granuleFilters, setGranuleFilters,

    // Pagination
    offset, limit,
    displayedOffset,
    handleReset, handleApply, handleNext, handlePrev,

    // Response
    plots, traits, granules,
    totalPlots, totalTraits, totalGranules,
    truncated, loading, error, setError,
    hasQueried,

    // Selected plot
    selectedPlotId, setSelectedPlotId,
    selectedTraits, selectedGranules,

    // Map
    mapData,
    filterMapData,

    // Download / pixel ranges
    getMergedDownloadData,
    getPixelRanges,

    // Pixel counts
    pagePixelCount,
    totalPixelCount,
    pixelCountLoading,
    totalCsvRows,
  };
}
