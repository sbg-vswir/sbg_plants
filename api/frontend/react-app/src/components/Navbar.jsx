import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton
} from '@mui/material';
import {
  Science as ScienceIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';

function Navbar({ view, views, onViewChange, onReset }) {
  return (
    <AppBar position="static" elevation={2}>
      <Toolbar>
        <ScienceIcon sx={{ mr: 2, fontSize: 32 }} />
        <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 600 }}>
          VSWIR Plants
        </Typography>
        
        {/* View Selector */}
        <FormControl variant="outlined" size="small" sx={{ minWidth: 200, bgcolor: 'white', borderRadius: 1 }}>
          <InputLabel>View</InputLabel>
          <Select value={view} onChange={onViewChange} label="View">
            {views.map(v => (
              <MenuItem key={v} value={v}>{v}</MenuItem>
            ))}
          </Select>
        </FormControl>
        
        <IconButton color="inherit" onClick={onReset} sx={{ ml: 2 }}>
          <RefreshIcon />
        </IconButton>
      </Toolbar>
    </AppBar>
  );
}

export default Navbar;
