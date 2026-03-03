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

  const response = await client.post(`/views/${view}`, payload, {
    responseType: 'arraybuffer'  // replaces response.arrayBuffer()
  });

  return parseParquetData(response.data, select);
}

/**
 * Start spectra extraction job
 */
export async function extractSpectra(pixelRangesBySensor) {
  const jobEntries = await Promise.all(
    Object.entries(pixelRangesBySensor).map(async ([sensorKey, pixelRanges]) => {
      const [campaign, sensor] = sensorKey.split('|');

      const metadata = await fetchParquet('extracted_metadata_view',
      {"campaign_name": campaign,
        "sensor_name": sensor,
      });

      // metadata is an array of rows — assuming one row per sensor
      const [wavelength_center, fwhm] = metadata.data[0];
      
      const payload = {
        view: 'extracted_spectra_view',
        format: 'parquet',
        debug: true,
        filters: { "pixel_id": pixelRanges },
        metadata: {
          campaign_name: campaign,
          sensor_name: sensor,
          "wavelength_center": wavelength_center,
          "fwhm": fwhm
        }
      };

      const response = await client.post('/views/extracted_spectra_view', payload);
      return [sensorKey, response.data.job_id];
    })
  );

  return Object.fromEntries(jobEntries);
}

export async function pollJobStatus(jobId, mode = 'individual') {
  try {
    const response = await client.get(`/job_status/${jobId}`, {
      params: { mode }
    });
    return response.data;
  } catch (err) {
    if (err.response?.status === 404) {
      if (mode === 'individual') return { status: 'queued', rowsProcessed: 0 };
      else if (mode === 'summary') return {};
      throw new Error('Error fetching job status');
    }
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
    const response = await client.post(`/isofit_run`, payload, {responseType: 'json'});
    return response;
}