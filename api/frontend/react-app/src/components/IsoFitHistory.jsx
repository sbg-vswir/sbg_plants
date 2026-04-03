import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Paper, Stack, Chip, CircularProgress,
  Alert, Select, MenuItem, Button, Divider, Tooltip, IconButton,
} from '@mui/material';
import {
  History as HistoryIcon,
  ContentCopy as CopyIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { listIsofitJobs } from '../utils/api';

const LIMIT_OPTIONS = [3, 5, 10, 20];

const STATUS_CHIP = {
  submitted: { color: 'default', label: 'Submitted' },
  running:   { color: 'warning', label: 'Running' },
  inverting: { color: 'warning', label: 'Inverting' },
  complete:  { color: 'success', label: 'Complete' },
  failed:    { color: 'error',   label: 'Failed' },
  partial:   { color: 'warning', label: 'Partial' },
  unknown:   { color: 'default', label: 'Unknown' },
};

function JobCard({ job, isActive, onMonitor }) {
  const chip = STATUS_CHIP[job.status] ?? { color: 'default', label: job.status };

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        borderColor: isActive ? 'primary.main' : 'divider',
        borderWidth: isActive ? 2 : 1,
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
        <Box sx={{ minWidth: 0 }}>
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mb: 0.5 }}>
            <Chip
              label={chip.label}
              color={chip.color}
              size="small"
            />
          </Stack>
          <Typography
            variant="caption"
            sx={{ fontFamily: 'monospace', color: 'text.secondary', display: 'block' }}
          >
            {job.job_id}
            <Tooltip title="Copy job ID">
              <IconButton
                size="small"
                sx={{ ml: 0.5, p: 0.2 }}
                onClick={() => navigator.clipboard.writeText(job.job_id)}
              >
                <CopyIcon sx={{ fontSize: 12 }} />
              </IconButton>
            </Tooltip>
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {job.submitted_by} · {new Date(job.created_at).toLocaleString()}
          </Typography>
        </Box>
        {!isActive && (
          <Button
            size="small"
            variant="outlined"
            onClick={() => onMonitor(job.job_id)}
            sx={{ textTransform: 'none', flexShrink: 0, ml: 1 }}
          >
            View
          </Button>
        )}
      </Stack>
    </Paper>
  );
}

export default function IsoFitHistory({ activeJobId, onMonitor }) {
  const [jobs, setJobs]       = useState([]);
  const [limit, setLimit]     = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [loaded, setLoaded]   = useState(false);

  async function load() {
    setLoading(true);
    setError('');
    try {
      setJobs(await listIsofitJobs(limit));
      setLoaded(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Only reload when limit changes if already loaded — don't auto-load on mount
  useEffect(() => {
    if (loaded) load();
  }, [limit]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Paper sx={{ p: 2 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <HistoryIcon fontSize="small" color="action" />
          <Typography variant="subtitle2" fontWeight={600}>Recent Jobs</Typography>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center">
          <Select
            size="small"
            value={limit}
            onChange={e => setLimit(e.target.value)}
            sx={{ fontSize: 13, height: 30 }}
          >
            {LIMIT_OPTIONS.map(n => (
              <MenuItem key={n} value={n} sx={{ fontSize: 13 }}>Show {n}</MenuItem>
            ))}
          </Select>
          <Tooltip title="Load / Refresh">
            <IconButton size="small" onClick={load} disabled={loading}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      </Stack>

      <Divider sx={{ mb: 1.5 }} />

      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

      {!loaded && !loading && (
        <Box sx={{ textAlign: 'center', py: 2 }}>
          <Button size="small" variant="outlined" onClick={load} startIcon={<HistoryIcon />}>
            Load Recent Jobs
          </Button>
        </Box>
      )}

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
          <CircularProgress size={24} />
        </Box>
      )}

      {loaded && !loading && jobs.length === 0 && (
        <Typography variant="body2" color="text.secondary">No jobs found.</Typography>
      )}

      {loaded && !loading && jobs.length > 0 && (
        <Stack spacing={1}>
          {jobs.map(job => (
            <JobCard
              key={job.job_id}
              job={job}
              isActive={job.job_id === activeJobId}
              onMonitor={onMonitor}
            />
          ))}
        </Stack>
      )}
    </Paper>
  );
}
