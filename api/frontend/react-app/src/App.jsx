import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import QueryPage from './pages/QueryPage';
import IsoFitPage from './pages/IsoFitPage';
import IngestPage from './pages/IngestPage';
import AdminPage from './pages/AdminPage';
import LoginButton from './components/LoginButton';
import { useIsAdmin } from './hooks/useIsAdmin';
import {
  getAuthCode,
  getStoredTokens,
  storeTokens,
  exchangeCodeForTokens,
  isTokenExpired,
} from './utils/auth';

// Redirects to / if the user doesn't have the required role
function RequireRole({ children, check }) {
  if (!check) return <Navigate to="/" replace />;
  return children;
}

function App() {
  const [authState, setAuthState] = useState('loading');
  const { isSuperAdmin, isAdmin }  = useIsAdmin();

  useEffect(() => {
    const tokens = getStoredTokens();
    const code   = getAuthCode();
    if (tokens && !isTokenExpired(tokens)) {
      setAuthState('loggedIn');
    } else if (code) {
      window.history.replaceState({}, document.title, '/');
      exchangeCodeForTokens(code)
        .then(t => { storeTokens(t); setAuthState('loggedIn'); })
        .catch(() => setAuthState('loggedOut'));
    } else {
      setAuthState('loggedOut');
    }
  }, []);

  if (authState === 'loading') return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
      <CircularProgress />
    </Box>
  );

  if (authState === 'loggedOut') return <LoginButton />;

  return (
    <Routes>
      <Route path="/" element={<QueryPage />} />

      <Route
        path="/admin"
        element={
          <RequireRole check={isAdmin}>
            <AdminPage />
          </RequireRole>
        }
      />

      <Route
        path="/isofit"
        element={
          <RequireRole check={isSuperAdmin}>
            <IsoFitPage />
          </RequireRole>
        }
      />

      <Route
        path="/ingest"
        element={
          <RequireRole check={isSuperAdmin}>
            <IngestPage />
          </RequireRole>
        }
      />

      {/* Catch-all — send unknown paths back to query */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
