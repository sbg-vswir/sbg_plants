import React, { useState } from 'react';
import {
  Box, Paper, Typography, Stack, Divider, IconButton, Collapse,
  Table, TableBody, TableCell, TableHead, TableRow,
} from '@mui/material';
import {
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';

const MISSING = new Set(['not recorded', 'not collected', 'unknown', 'n/a', '']);
const present  = (v) => v != null && !MISSING.has(String(v).toLowerCase().trim());
const dateStr  = (v) => (v ? String(v).slice(0, 10) : null);

function Row({ label, value }) {
  if (!present(value) && value !== 0) return null;
  return (
    <Stack direction="row" spacing={1} sx={{ py: 0.25 }}>
      <Typography variant="caption" color="text.secondary" sx={{ minWidth: 120, flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography variant="caption">{value}</Typography>
    </Stack>
  );
}

function Section({ title, count, children }) {
  const [open, setOpen] = useState(true);
  return (
    <>
      <Stack
        direction="row" alignItems="center" justifyContent="space-between"
        sx={{ cursor: 'pointer', mb: open ? 1 : 0 }}
        onClick={() => setOpen(v => !v)}
      >
        <Typography variant="subtitle2" color="text.secondary">
          {title} ({count})
        </Typography>
        <IconButton size="small" tabIndex={-1}>
          {open ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
        </IconButton>
      </Stack>
      <Collapse in={open}>
        {children}
      </Collapse>
    </>
  );
}

function GranuleCard({ g }) {
  const [open, setOpen] = useState(false);
  return (
    <Box
      sx={{
        borderRadius: 1,
        border: '1px solid',
        borderColor: 'grey.200',
        overflow: 'hidden',
      }}
    >
      {/* Always-visible header row */}
      <Stack
        direction="row" alignItems="center" spacing={1}
        sx={{ px: 1.5, py: 1, cursor: 'pointer', bgcolor: 'grey.50' }}
        onClick={() => setOpen(v => !v)}
      >
        <Typography variant="caption" sx={{ fontWeight: 600, fontFamily: 'monospace', flex: 1 }}>
          {g.granule_id}
        </Typography>
        {present(g.cloudy_conditions) && (
          <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
            {g.cloudy_conditions}
          </Typography>
        )}
        <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
          {dateStr(g.acquisition_date) ?? ''}
        </Typography>
        <IconButton size="small" tabIndex={-1}>
          {open ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
        </IconButton>
      </Stack>

      {/* Expandable detail */}
      <Collapse in={open}>
        <Box sx={{ px: 1.5, pb: 1.5, pt: 0.5, bgcolor: 'white' }}>
          <Row label="Campaign"       value={g.campaign_name} />
          <Row label="Sensor"         value={g.sensor_name} />
          <Row label="Date"           value={dateStr(g.acquisition_date)} />
          <Row label="Time"           value={g.acquisition_start_time} />
          <Row label="Sky conditions" value={present(g.cloudy_conditions) ? g.cloudy_conditions : null} />
          <Row label="Cloud type"     value={present(g.cloud_type)        ? g.cloud_type        : null} />
          <Row label="Pixels"         value={Array.isArray(g.pixel_ids)   ? g.pixel_ids.length  : null} />
        </Box>
      </Collapse>
    </Box>
  );
}

function PlotSidePanel({ plotId, traits, granules, onClose }) {
  if (!plotId) return null;

  const plotName = traits[0]?.plot_name;

  return (
    <Paper
      elevation={4}
      sx={{
        width: 380,
        minWidth: 320,
        maxHeight: 'calc(100vh - 80px)',
        overflowY: 'auto',
        p: 2,
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 0.5 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600, lineHeight: 1.2 }}>
            Plot {plotId}
          </Typography>
          {present(plotName) && (
            <Typography variant="caption" color="text.secondary">{plotName}</Typography>
          )}
        </Box>
        <IconButton size="small" onClick={onClose}><CloseIcon /></IconButton>
      </Stack>

      <Divider sx={{ my: 1.5 }} />

      {/* Traits — collapsible, vertically scrollable */}
      <Section title="Trait measurements" count={traits.length}>
        {traits.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            No trait measurements for this plot.
          </Typography>
        ) : (
          <Box sx={{ overflowX: 'auto', mb: 2, maxHeight: 260, overflowY: 'auto' }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  {['Trait', 'Value', 'Units', 'Date', 'Taxa'].map(h => (
                    <TableCell key={h} sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {traits.map((t, i) => (
                  <TableRow key={i} hover>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{present(t.trait) ? t.trait : '—'}</TableCell>
                    <TableCell>{t.value != null  ? t.value  : '—'}</TableCell>
                    <TableCell>{present(t.units) ? t.units  : '—'}</TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{dateStr(t.collection_date) ?? '—'}</TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{present(t.taxa) ? t.taxa : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
      </Section>

      <Divider sx={{ mb: 1.5 }} />

      {/* Granules — collapsible section, each card also collapsible */}
      <Section title="Overlapping granules" count={granules.length}>
        {granules.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No overlapping granules for this plot.
          </Typography>
        ) : (
          <Stack spacing={1}>
            {granules.map((g, i) => (
              <GranuleCard key={i} g={g} />
            ))}
          </Stack>
        )}
      </Section>
    </Paper>
  );
}

export default PlotSidePanel;
