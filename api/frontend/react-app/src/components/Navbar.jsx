import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar, Toolbar, Typography,
  IconButton, Box, Button, Tooltip, Tabs, Tab,
} from '@mui/material';
import { Logout as LogoutIcon } from '@mui/icons-material';
import { redirectToLogout } from '../utils/auth';
import { useIsAdmin } from '../hooks/useIsAdmin';

function Navbar({ showControls = true }) {
  const { isAdmin, isSuperAdmin } = useIsAdmin();
  const navigate  = useNavigate();
  const location  = useLocation();

  // Map pathname to tab value — unknown paths fall back to false (no tab highlighted)
  const TAB_PATHS = ['/', '/isofit', '/ingest', '/admin'];
  const currentTab = TAB_PATHS.includes(location.pathname) ? location.pathname : false;

  return (
    <>
      <AppBar position="fixed" elevation={2}>
        <Toolbar sx={{ display: 'flex', justifyContent: 'space-between', minHeight: 56 }}>

          {/* Left — title */}
          <Typography variant="h6" sx={{ fontWeight: 600, mr: 3, whiteSpace: 'nowrap' }}>
            VSWIR Plants
          </Typography>

          {/* Centre — persistent nav tabs */}
          <Tabs
            value={currentTab}
            onChange={(_, val) => navigate(val)}
            textColor="inherit"
            TabIndicatorProps={{ style: { backgroundColor: 'white', height: 3 } }}
            sx={{ flex: 1 }}
          >
            <Tab
              label="Query"
              value="/"
              sx={{ textTransform: 'none', fontWeight: 500, color: 'rgba(255,255,255,0.8)',
                    '&.Mui-selected': { color: 'white' } }}
            />
            {isSuperAdmin && (
              <Tab
                label="ISOFIT"
                value="/isofit"
                sx={{ textTransform: 'none', fontWeight: 500, color: 'rgba(255,255,255,0.8)',
                      '&.Mui-selected': { color: 'white' } }}
              />
            )}
            {isAdmin && (
              <Tab
                label="Ingest"
                value="/ingest"
                sx={{ textTransform: 'none', fontWeight: 500, color: 'rgba(255,255,255,0.8)',
                      '&.Mui-selected': { color: 'white' } }}
              />
            )}
            {isAdmin && (
              <Tab
                label="Admin"
                value="/admin"
                sx={{ textTransform: 'none', fontWeight: 500, color: 'rgba(255,255,255,0.8)',
                      '&.Mui-selected': { color: 'white' } }}
              />
            )}
          </Tabs>

          {/* Right — logout */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>

            <Button
              color="inherit"
              onClick={redirectToLogout}
              startIcon={<LogoutIcon />}
              sx={{ textTransform: 'none', fontWeight: 500 }}
            >
              Logout
            </Button>
          </Box>

        </Toolbar>
      </AppBar>
      <Toolbar />
    </>
  );
}

export default Navbar;
