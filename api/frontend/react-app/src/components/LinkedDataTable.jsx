import React, { useState } from 'react';
import {
  Paper, Typography, Box, Tab, Tabs,
  Table, TableBody, TableCell, TableHead, TableRow,
  Collapse, IconButton, Tooltip,
} from '@mui/material';
import {
  ExpandLess as ExpandLessIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';

function LinkedDataTable({ traits, granules, totalTraits, totalGranules }) {
  const [tab, setTab]           = useState(0);
  const [collapsed, setCollapsed] = useState(false);

  const traitLabel   = totalTraits   != null && totalTraits   !== traits.length
    ? `Traits (${traits.length} of ${totalTraits})`
    : `Traits (${traits.length})`;

  const granuleLabel = totalGranules != null && totalGranules !== granules.length
    ? `Granules (${granules.length} of ${totalGranules})`
    : `Granules (${granules.length})`;

  return (
    <Paper elevation={2} sx={{ mt: 3 }}>
      <Box sx={{ borderBottom: collapsed ? 0 : 1, borderColor: 'divider', px: 2, pt: 1, display: 'flex', alignItems: 'center' }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ flex: 1 }}>
          <Tab label={traitLabel} />
          <Tab label={granuleLabel} />
        </Tabs>
        <Tooltip title={collapsed ? 'Expand table' : 'Collapse table'}>
          <IconButton size="small" onClick={() => setCollapsed(c => !c)} sx={{ ml: 1 }}>
            {collapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
          </IconButton>
        </Tooltip>
      </Box>

      <Collapse in={!collapsed} unmountOnExit>
        {tab === 0 && <TraitsTab traits={traits} />}
        {tab === 1 && <GranulesTab granules={granules} />}
      </Collapse>
    </Paper>
  );
}

function TraitsTab({ traits }) {
  const COLS = [
    { label: 'Campaign',        key: 'campaign_name' },
    { label: 'Site',            key: 'site_id' },
    { label: 'Plot name',       key: 'plot_name' },
    { label: 'Sample',          key: 'sample_name' },
    { label: 'Collection date', key: 'collection_date', date: true },
    { label: 'Trait',           key: 'trait' },
    { label: 'Value',           key: 'value' },
    { label: 'Units',           key: 'units' },
    { label: 'Taxa',            key: 'taxa' },
    { label: 'Veg/cover type',  key: 'veg_or_cover_type' },
    { label: 'Phenophase',      key: 'phenophase' },
    { label: 'FC class',        key: 'sample_fc_class' },
    { label: 'FC %',            key: 'sample_fc_percent' },
    { label: 'Canopy position', key: 'canopy_position' },
    { label: 'Plant status',    key: 'plant_status' },
    { label: 'Plot veg type',   key: 'plot_veg_type' },
    { label: 'Cover method',    key: 'subplot_cover_method' },
    { label: 'Method',          key: 'method' },
    { label: 'Handling',        key: 'handling' },
    { label: 'Error',           key: 'error' },
    { label: 'Error type',      key: 'error_type' },
  ];

  return (
    <Box sx={{ overflowX: 'auto', maxHeight: 480, overflowY: 'auto' }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            {COLS.map(c => (
              <TableCell key={c.key} sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{c.label}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {traits.length === 0 ? (
            <TableRow>
              <TableCell colSpan={COLS.length} align="center">
                <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                  No trait data for current filters.
                </Typography>
              </TableCell>
            </TableRow>
          ) : traits.map((t, i) => (
            <TableRow key={i} hover>
              {COLS.map(c => (
                <TableCell key={c.key} sx={{ whiteSpace: 'nowrap' }}>
                  {c.date
                    ? (t[c.key] ? String(t[c.key]).slice(0, 10) : '—')
                    : (t[c.key] != null ? t[c.key] : '—')}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

function GranulesTab({ granules }) {
  return (
    <Box sx={{ overflowX: 'auto', maxHeight: 480, overflowY: 'auto' }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            {['Granule ID', 'Campaign', 'Sensor', 'Acquisition date', 'Cloudy conditions', 'Cloud type', 'Plots', 'Pixels'].map(h => (
              <TableCell key={h} sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {granules.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} align="center">
                <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                  No granule data for current filters.
                </Typography>
              </TableCell>
            </TableRow>
          ) : granules.map((g, i) => (
            <TableRow key={i} hover>
              <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{g.granule_id}</TableCell>
              <TableCell>{g.campaign_name || '—'}</TableCell>
              <TableCell>{g.sensor_name || '—'}</TableCell>
              <TableCell>{g.acquisition_date ? String(g.acquisition_date).slice(0, 10) : '—'}</TableCell>
              <TableCell>{g.cloudy_conditions || '—'}</TableCell>
              <TableCell>{g.cloud_type || '—'}</TableCell>
              <TableCell>{Array.isArray(g.plot_ids) ? g.plot_ids.length : '—'}</TableCell>
              <TableCell>{Array.isArray(g.pixel_ids) ? g.pixel_ids.length : '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

export default LinkedDataTable;
