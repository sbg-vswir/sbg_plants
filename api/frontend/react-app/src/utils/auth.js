const COGNITO_DOMAIN      = import.meta.env.VITE_COGNITO_DOMAIN;
export const COGNITO_CLIENT_ID    = import.meta.env.VITE_COGNITO_CLIENT_ID;
export const COGNITO_REDIRECT_URI = import.meta.env.VITE_COGNITO_REDIRECT_URI;
const COGNITO_LOGOUT_URI  = import.meta.env.VITE_COGNITO_LOGOUT_URI;

// Redirect user to Cognito hosted UI login
export function redirectToLogin() {
  const url = new URL(`${COGNITO_DOMAIN}/login`);
  url.searchParams.set('client_id', COGNITO_CLIENT_ID);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('scope', 'openid email profile');
  url.searchParams.set('redirect_uri', COGNITO_REDIRECT_URI);
  window.location.href = url.toString();
}

export function redirectToLogout() {
  clearTokens();
  const url = new URL(`${COGNITO_DOMAIN}/logout`);
  url.searchParams.set('client_id', COGNITO_CLIENT_ID);
  url.searchParams.set('logout_uri', COGNITO_LOGOUT_URI);
  window.location.href = url.toString();
}

export async function exchangeCodeForTokens(code) {
  const response = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type:   'authorization_code',
      client_id:    COGNITO_CLIENT_ID,
      redirect_uri: COGNITO_REDIRECT_URI,
      code,
    }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error_description || data.error || 'Token exchange failed');
  }
  return data;
}

// Use a stored refresh_token to get a new id_token + access_token.
// Returns the updated token set, or throws if the refresh_token is expired/invalid.
export async function refreshTokens(tokens) {
  if (!tokens?.refresh_token) throw new Error('No refresh token available');

  const response = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type:    'refresh_token',
      client_id:     COGNITO_CLIENT_ID,
      refresh_token: tokens.refresh_token,
    }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error_description || data.error || 'Token refresh failed');
  }

  // Cognito does not return a new refresh_token on refresh — carry the old one forward
  return { ...tokens, ...data };
}

// Get OAuth code from URL query params
export function getAuthCode() {
  const params = new URLSearchParams(window.location.search);
  return params.get('code');
}

// Token storage — sessionStorage so tokens are cleared when the tab/browser closes
// and are not accessible to other tabs or persistent scripts.
const TOKEN_KEY = 'cognito_tokens';

export function storeTokens(tokens) {
  sessionStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
}

export function getStoredTokens() {
  const t = sessionStorage.getItem(TOKEN_KEY);
  return t ? JSON.parse(t) : null;
}

export function clearTokens() {
  sessionStorage.removeItem(TOKEN_KEY);
}

// Decode the id_token JWT payload to get user info (no verification needed client-side).
// Handles base64url encoding (no padding, + and / replaced with - and _).
export function getUserFromTokens(tokens) {
  if (!tokens?.id_token) return null;
  try {
    const raw     = tokens.id_token.split('.')[1];
    const padded  = raw.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(raw.length / 4) * 4, '=');
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

// Check if the id_token is expired
export function isTokenExpired(tokens) {
  const user = getUserFromTokens(tokens);
  if (!user?.exp) return true;
  return Date.now() >= user.exp * 1000;
}
