import axios from 'axios';
import { getStoredTokens, storeTokens, clearTokens, refreshTokens, redirectToLogin } from './auth';

const BASE = import.meta.env.VITE_API_BASE_URL || 'https://iuzni7mumj.execute-api.us-west-2.amazonaws.com';

const client = axios.create({ baseURL: BASE });

// Attach the current id_token to every outgoing request
client.interceptors.request.use((config) => {
  const tokens = getStoredTokens();
  if (tokens?.id_token) {
    config.headers.Authorization = `Bearer ${tokens.id_token}`;
  }
  return config;
});

// On 401 — attempt a token refresh once, then retry the original request.
// If the refresh fails, clear tokens and redirect to login.
let isRefreshing = false;
let refreshQueue = []; // requests waiting for the refresh to complete

function processQueue(error, token = null) {
  refreshQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token);
  });
  refreshQueue = [];
}

client.interceptors.response.use(
  response => response,
  async error => {
    const original = error.config;

    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      // Another request already triggered a refresh — queue this one until it resolves
      return new Promise((resolve, reject) => {
        refreshQueue.push({ resolve, reject });
      }).then(token => {
        original.headers.Authorization = `Bearer ${token}`;
        return client(original);
      });
    }

    original._retry  = true;
    isRefreshing     = true;

    try {
      const tokens    = getStoredTokens();
      const refreshed = await refreshTokens(tokens);
      storeTokens(refreshed);
      processQueue(null, refreshed.id_token);
      original.headers.Authorization = `Bearer ${refreshed.id_token}`;
      return client(original);
    } catch (refreshError) {
      processQueue(refreshError);
      clearTokens();
      redirectToLogin();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

// -----------------------------------------------------------------------
// Cold-start retry — query-page traffic only.
//
// A Lambda cold start can occasionally surface to the client as a bare
// HTTP 500 (the container fails/crashes during init, before our own
// handler code ever runs to produce a proper error response). A couple of
// bounded retries gives the next attempt a chance to land on an
// already-warm container.
//
// Scoped deliberately to read-only "query page" traffic — GET requests,
// plus POST /query* (which are semantically SELECT queries server-side,
// see database_api/app/main.py — no writes happen on these routes even
// though they use POST). This intentionally excludes mutation endpoints
// (/admin/*, /ingest/*, /run_isofit, algorithm job submission, etc.) —
// retrying those could duplicate a real side effect (e.g. submit a second
// AWS Batch job, create a duplicate user) if the original request actually
// completed server-side before the response failed to come back.
// -----------------------------------------------------------------------
const MAX_COLD_START_RETRIES = 2;
const COLD_START_RETRY_DELAYS_MS = [300, 800];

function isRetryableQueryRequest(config) {
  const method = (config.method || 'get').toLowerCase();
  if (method === 'get') return true;
  if (method === 'post') {
    const path = (config.url || '').split('?')[0];
    return path === '/query' || path.startsWith('/query/');
  }
  return false;
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

client.interceptors.response.use(
  response => response,
  async error => {
    const original = error.config;

    if (
      !original ||
      error.response?.status !== 500 ||
      !isRetryableQueryRequest(original)
    ) {
      return Promise.reject(error);
    }

    const attempt = original._coldStartRetryCount || 0;
    if (attempt >= MAX_COLD_START_RETRIES) {
      return Promise.reject(error);
    }

    original._coldStartRetryCount = attempt + 1;
    await delay(COLD_START_RETRY_DELAYS_MS[attempt] ?? COLD_START_RETRY_DELAYS_MS.at(-1));
    return client(original);
  }
);

export default client;
