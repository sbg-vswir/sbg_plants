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
  running:  { color: 'primary',  label: 'Running' },
  complete: { color: 'success',  label: 'Complete' },
  failed:   { color: 'error',    label: 'Failed' },
};

function JobCard({ job, isActive, onMonitor }) {
  const chip  = STATUS_CHIP[job.status] ?? { color: 'default', label: job.status };
  const isRunning = job.status === 'running';

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
              icon={isRunning ? <CircularProgress size={10} color="inherit" /> : undefined}
            />
            {isActive && (
              <Chip label="Active" size="small" variant="outlined" color="primary" />
            )}
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
            Monitor
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

  async function load() {
    setLoading(true);
    setError('');
    try {
      setJobs(await listIsofitJobs(limit));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Reload when limit changes or a new active job comes in
  useEffect(() => { load(); }, [limit, activeJobId]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Paper sx={{ p: 2, mt: 2 }}>
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
          <Tooltip title="Refresh">
            <IconButton size="small" onClick={load} disabled={loading}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      </Stack>

      <Divider sx={{ mb: 1.5 }} />

      {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
          <CircularProgress size={24} />
        </Box>
      ) : jobs.length === 0 ? (
        <Typography variant="body2" color="text.secondary">No jobs found.</Typography>
      ) : (
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
