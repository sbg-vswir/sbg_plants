import React, { useState } from 'react';
import { AppBar, Toolbar, Typography, Select, MenuItem, IconButton, Box, Button, Tooltip } from '@mui/material';
import { Refresh as RefreshIcon, Logout as LogoutIcon } from '@mui/icons-material';
import { AdminPanelSettings as AdminIcon, Science as IsoFitIcon, Home as HomeIcon } from '@mui/icons-material';
import { redirectToLogout } from '../utils/auth';
import { useIsAdmin } from '../hooks/useIsAdmin';
import AdminDialog from './AdminDialog';

function Navbar({ view, views, onViewChange, onReset, showControls = true, onIsoFitClick, onHomeClick, isIsoFitMode }) {
  const { isAdmin, isSuperAdmin } = useIsAdmin();
  const [adminOpen, setAdminOpen] = useState(false);

  return (
    <>
      <AppBar position="fixed" elevation={2}>
        <Toolbar sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {onHomeClick && (
              <Tooltip title="Back to main">
                <IconButton color="inherit" onClick={onHomeClick} size="small">
                  <HomeIcon />
                </IconButton>
              </Tooltip>
            )}
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              VSWIR Plants
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {showControls && (
              <>
                <Select
                  value={view}
                  onChange={onViewChange}
                  variant="standard"
                  sx={{ color: 'white', '& .MuiSelect-icon': { color: 'white' }, minWidth: 120 }}
                >
                  {views.map(v => <MenuItem key={v} value={v}>{v}</MenuItem>)}
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

            {isSuperAdmin && (
              <Button
                color="inherit"
                onClick={onIsoFitClick}
                startIcon={<IsoFitIcon />}
                sx={{
                  textTransform: 'none',
                  fontWeight: 500,
                  ...(isIsoFitMode && {
                    bgcolor: 'rgba(255,255,255,0.15)',
                    borderRadius: 1,
                  })
                }}
              >
                {isIsoFitMode ? 'Spectral Mode' : 'ISOFIT Mode'}
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