// api/api.js
import client from './client';
import { parseParquetData } from './parquetUtils';
import { SELECT_CONFIGS } from '../viewConfig';

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

  let response;
  try {
    response = await client.post(`/views/${view}`, payload, {
      responseType: 'arraybuffer'
    });
  } catch (err) {
    // Axios puts the error response on err.response.
    // Because we requested arraybuffer, the body is a raw buffer — decode it.
    const raw = err.response?.data;
    if (raw instanceof ArrayBuffer) {
      try {
        const text = new TextDecoder().decode(raw);
        const json = JSON.parse(text);
        const status = err.response.status;
        if (status === 404) throw new Error('No data found for the selected filters.');
        throw new Error(json.error || json.message || `Request failed (${status})`);
      } catch (inner) {
        if (inner.message) throw inner;
      }
    }
    throw new Error(err.message || 'Request failed');
  }

  return parseParquetData(response.data, select);
}

/**
 * Start spectra extraction job.
 * spectraType: 'radiance' | 'reflectance'
 */
export async function extractSpectra(pixelRangesBySensor, spectraType = 'radiance') {
  const view = spectraType === 'reflectance' ? 'reflectance_view' : 'extracted_spectra_view';

  const jobEntries = await Promise.all(
    Object.entries(pixelRangesBySensor).map(async ([sensorKey, pixelRanges]) => {
      const [campaign, sensor] = sensorKey.split('|');

      // Both radiance and reflectance need wavelength/fwhm for column headers
      const metadata = await fetchParquet('extracted_metadata_view', {
        campaign_name: campaign,
        sensor_name: sensor,
      });

      const [wavelength_center, fwhm] = metadata.data[0];

      const payload = {
        view,
        format: 'parquet',
        filters: { pixel_id: pixelRanges },
        metadata: {
          campaign_name: campaign,
          sensor_name: sensor,
          wavelength_center,
          fwhm,
          spectral_column: spectraType === 'reflectance' ? 'reflectance' : 'radiance',
        },
      };

      const response = await client.post(`/views/${view}`, payload);
      return [sensorKey, response.data.job_id];
    })
  );

  return Object.fromEntries(jobEntries);
}

export async function pollJobStatus(jobId, mode = 'single') {
  try {
    const response = await client.get(`/job_status/${jobId}`, {
      params: { mode }
    });
    return response.data;
  } catch (err) {
    if (err.response?.status === 404) {
      if (mode === 'single') return { status: 'queued', rowsProcessed: 0 };
      if (mode === 'summary') return {};
    }
    throw new Error('Error fetching job status');
  }
}

/**
 * Admin API calls
 */
export const adminApi = {
  listUsers: () =>
    client.get('/admin/users').then(r => r.data),

  createUser: (data) =>
    client.post('/admin/users', data).then(r => r.data),

  deleteUser: (username) =>
    client.delete(`/admin/users/${username}`).then(r => r.data),

  addToGroup: (username, group) =>
    client.post(`/admin/users/${username}/groups`, { group }).then(r => r.data),

  removeFromGroup: (username, group) =>
    client.delete(`/admin/users/${username}/groups/${group}`).then(r => r.data),
};

export async function submitIsofitRun(payload) {
    const response = await client.post(`/run_isofit`, payload, {responseType: 'json'});
    return response;
}

export async function listIsofitJobs(limit = 5) {
  const response = await client.get('/isofit_jobs', { params: { limit } });
  return response.data.jobs;
}

/**
 * Ingestion API calls
 */
export const ingestApi = {
  // Upload a bundle of 6 files — returns { batch_id }
  submitBatch: (files) => {
    const form = new FormData();
    Object.entries(files).forEach(([key, file]) => form.append(key, file));
    return client.post('/ingest', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },

  // List all batches for the current user
  listBatches: () =>
    client.get('/ingest').then(r => r.data),

  // Get a single batch — includes qaqc_report
  getBatch: (batchId) =>
    client.get(`/ingest/${batchId}`).then(r => r.data),

  // Approve a QAQC_PASS batch
  approveBatch: (batchId) =>
    client.post(`/ingest/${batchId}/approve`).then(r => r.data),

  // Reject a batch
  rejectBatch: (batchId) =>
    client.post(`/ingest/${batchId}/reject`).then(r => r.data),
};