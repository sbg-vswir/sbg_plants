// api/client.js
import axios from 'axios';

const BASE = 'https://iuzni7mumj.execute-api.us-west-2.amazonaws.com';

const client = axios.create({ baseURL: BASE });

client.interceptors.request.use((config) => {
  const stored = localStorage.getItem('cognito_tokens');
  const parsed = stored ? JSON.parse(stored) : null;
  if (parsed?.id_token) {
    config.headers.Authorization = `Bearer ${parsed.id_token}`;
  }
  return config;
});

export default client;