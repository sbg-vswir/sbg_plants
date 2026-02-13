import { parseParquetData } from './parquetUtils';
import { SELECT_CONFIGS } from '../viewConfig';

const API_URL = "https://iuzni7mumj.execute-api.us-west-2.amazonaws.com/views/{}";
const JOB_STATUS_URL = "https://iuzni7mumj.execute-api.us-west-2.amazonaws.com/job_status/{}";

/**
 * Fetch Parquet data from API
 */
export async function fetchParquet(view, filters, limit = null, offset = 0) {
  const select = SELECT_CONFIGS[view];
  const payload = {
    view,
    format: 'parquet',
    select,
    offset,
    debug: true
  };

  if (limit !== null && Number.isInteger(limit)) {
    payload.limit = limit;
  }

  const validFilters = Object.fromEntries(
    Object.entries(filters).filter(([_, v]) => v !== null && v !== undefined)
  );
  
  if (Object.keys(validFilters).length > 0) {
    payload.filters = validFilters;
  }

  // console.log('Fetching with filters:', filters);

  const url = API_URL.replace('{}', view);
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  return parseParquetData(arrayBuffer, select);
}

/**
 * Start spectra extraction job
 */
export async function extractSpectra(pixelRanges) {
  const params = {
    view: 'extracted_spectra_view',
    format: 'parquet',
    debug: true,
    filters: { pixel_id: pixelRanges }
  };
  
  const url = API_URL.replace('{}', 'extracted_spectra_view');
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  
  if (!response.ok) {
    throw new Error(`Spectra extraction failed: ${response.status}`);
  }
  
  const data = await response.json();
  return data.job_id;
}

/**
 * Poll job status
 */
export async function pollJobStatus(jobId) {
  const url = JOB_STATUS_URL.replace('{}', jobId);
  const response = await fetch(url);
  
  if (response.status === 404) {
    return { status: 'queued', rowsProcessed: 0 };
  }
  
  if (!response.ok) {
    throw new Error('Error fetching job status');
  }
  
  const data = await response.json();
  return {
    status: data.presigned_url ? 'complete' : 'running',
    rowsProcessed: data.rows_processed || 0,
    downloadUrl: data.presigned_url
  };
}
