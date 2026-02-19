import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Select,
  MenuItem,
  IconButton,
  Box,
  Button
} from '@mui/material';
import { Refresh as RefreshIcon, Logout as LogoutIcon } from '@mui/icons-material';
import { redirectToLogout } from '../utils/auth';

function Navbar({ view, views, onViewChange, onReset, showControls = true }) {
  return (
    <>
      <AppBar position="fixed" elevation={2}>
        <Toolbar sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            VSWIR Plants
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {/* Only show view selector and reset when logged in */}
            {showControls && (
              <>
                <Select
                  value={view}
                  onChange={onViewChange}
                  variant="standard"
                  sx={{
                    color: 'white',
                    '& .MuiSelect-icon': { color: 'white' },
                    minWidth: 120
                  }}
                >
                  {views.map(v => (
                    <MenuItem key={v} value={v}>
                      {v}
                    </MenuItem>
                  ))}
                </Select>

                <IconButton color="inherit" onClick={onReset} title="Reset">
                  <RefreshIcon />
                </IconButton>
              </>
            )}

            {/* Logout always visible when navbar is shown */}
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

      {/* Spacer to avoid overlap with fixed AppBar */}
      <Toolbar />
    </>
  );
}

export default Navbar;
