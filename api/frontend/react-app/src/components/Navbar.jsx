import React, { useState } from 'react';
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
import { AdminPanelSettings as AdminIcon } from '@mui/icons-material';
import { redirectToLogout } from '../utils/auth';
import { useIsAdmin } from '../hooks/useIsAdmin';
import AdminDialog from './AdminDialog';

function Navbar({ view, views, onViewChange, onReset, showControls = true }) {
  const { isAdmin } = useIsAdmin();
  const [adminOpen, setAdminOpen] = useState(false);

  return (
    <>
      <AppBar position="fixed" elevation={2}>
        <Toolbar sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            VSWIR Plants
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
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
                    <MenuItem key={v} value={v}>{v}</MenuItem>
                  ))}
                </Select>

                <IconButton color="inherit" onClick={onReset} title="Reset">
                  <RefreshIcon />
                </IconButton>
              </>
            )}

            {isAdmin && (
              <Button
                color="inherit"
                onClick={() => setAdminOpen(true)}
                startIcon={<AdminIcon />}
                sx={{ textTransform: 'none', fontWeight: 500 }}
              >
                Admin
              </Button>
            )}

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

      <AdminDialog open={adminOpen} onClose={() => setAdminOpen(false)} />
    </>
  );
}

export default Navbar;