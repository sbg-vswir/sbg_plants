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

export default client;
