const COGNITO_DOMAIN = import.meta.env.VITE_COGNITO_DOMAIN;
export const COGNITO_CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID;
export const COGNITO_REDIRECT_URI = import.meta.env.VITE_COGNITO_REDIRECT_URI;
const COGNITO_LOGOUT_URI = import.meta.env.VITE_COGNITO_LOGOUT_URI;

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
  // console.log('attempting exchange with:', {
  //   domain: COGNITO_DOMAIN,
  //   client_id: COGNITO_CLIENT_ID,
  //   redirect_uri: COGNITO_REDIRECT_URI,
  //   code
  // });

  const response = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: COGNITO_CLIENT_ID,
      redirect_uri: COGNITO_REDIRECT_URI,
      code,
    }),
  });

  const data = await response.json();
  // console.log('token response:', data); // logs error OR tokens

  if (!response.ok) {
    throw new Error(data.error_description || data.error || 'Token exchange failed');
  }

  return data;
}

// Get OAuth code from URL query params
export function getAuthCode() {
  const params = new URLSearchParams(window.location.search);
  return params.get('code');
}

// Token storage
export function storeTokens(tokens) {
  localStorage.setItem('cognito_tokens', JSON.stringify(tokens));
}

export function getStoredTokens() {
  const t = localStorage.getItem('cognito_tokens');
  return t ? JSON.parse(t) : null;
}

export function clearTokens() {
  localStorage.removeItem('cognito_tokens');
}

// Decode the id_token JWT payload to get user info (no verification needed client-side)
export function getUserFromTokens(tokens) {
  if (!tokens?.id_token) return null;
  try {
    const payload = tokens.id_token.split('.')[1];
    return JSON.parse(atob(payload));
    // contains email, sub, cognito:username, exp, etc.
  } catch {
    return null;
  }
}

// Check if the access token is expired
export function isTokenExpired(tokens) {
  if (!tokens?.id_token) return true;
  try {
    const payload = JSON.parse(atob(tokens.id_token.split('.')[1]));
    return Date.now() >= payload.exp * 1000;
  } catch {
    return true;
  }
}