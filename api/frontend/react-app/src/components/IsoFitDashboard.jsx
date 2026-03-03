import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Paper, Grid, Button, TextField, Chip,
  LinearProgress, Alert, CircularProgress, Divider,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Tooltip, IconButton
} from '@mui/material';
import {
  PlayArrow as RunIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  History as HistoryIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  HourglassEmpty as PendingIcon,
  ContentCopy as CopyIcon
} from '@mui/icons-material';
import { useIsoFitPolling } from '../hooks/useIsoFitPolling';
import { client } from '../utils/api';

const STORAGE_KEY = 'isofit_job_history';
const MAX_HISTORY = 10;
const ACTIVE_JOB_KEY = 'isofit_active_job';

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveHistory(history) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
}

function StatusChip({ status }) {
  const map = {
    complete: { color: 'success', icon: <SuccessIcon fontSize="small" /> },
    running:  { color: 'primary', icon: <CircularProgress size={12} /> },
    failed:   { color: 'error',   icon: <ErrorIcon fontSize="small" /> },
    queued:   { color: 'default', icon: <PendingIcon fontSize="small" /> },
  };
  const { color, icon } = map[status] ?? map.queued;
  return <Chip label={status} color={color} size="small" icon={icon} />;
}

function MetricCard({ label, value, color }) {
  return (
    <Paper
      elevation={1}
      sx={{ p: 2, textAlign: 'center', borderTop: 3, borderColor: color || 'primary.main' }}
    >
      <Typography variant="h4" fontWeight={700} color={color || 'primary.main'}>
        {value ?? '—'}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        {label}
      </Typography>
    </Paper>
  );
}

export default function IsoFitDashboard({ initialJobId, onJobStarted }) {
  // Use ACTIVE_JOB_KEY if initialJobId is null
  const [parentJobId, setParentJobId] = useState(() => {
    return initialJobId || localStorage.getItem(ACTIVE_JOB_KEY) || '';
  });
  const [isPolling, setIsPolling] = useState(!!parentJobId);
  const [history, setHistory] = useState(loadHistory);
  const { jobData, pollingError, lastUpdated, isComplete } = useIsoFitPolling(parentJobId, isPolling);

  // Persist active job in localStorage
  useEffect(() => {
    if (!parentJobId) return;
    localStorage.setItem(ACTIVE_JOB_KEY, parentJobId);
  }, [parentJobId]);

  // Add job to history once we have jobData from Lambda
  useEffect(() => {
    if (!jobData?.parent_job_id) return;
    setHistory(prev => {
      const exists = prev.find(h => h.id === jobData.parent_job_id);
      if (exists) return prev;
      const entry = { id: jobData.parent_job_id, startedAt: jobData.created_at };
      const next = [entry, ...prev];
      saveHistory(next);
      return next;
    });
  }, [jobData?.parent_job_id, jobData?.created_at]);

  // Clear ACTIVE_JOB_KEY when job completes
  useEffect(() => {
    if (isComplete && parentJobId) {
      localStorage.removeItem(ACTIVE_JOB_KEY);
    }
  }, [isComplete, parentJobId]);

  // When launching a new job
  const handleLaunch = async () => {
    try {
      const response = await client.post('/isofit_run'); // your Lambda
      const id = response.data.parent_job_id;
      setParentJobId(id);
      setIsPolling(true);
      onJobStarted?.(id);
      // Add to history immediately
      setHistory(prev => {
        const exists = prev.find(h => h.id === id);
        if (exists) return prev;
        const entry = { id, startedAt: response.data.created_at };
        const next = [entry, ...prev];
        saveHistory(next);
        return next;
      });
    } catch (err) {
      console.error('Launch failed', err);
    }
  };

  const handleMonitor = () => {
    if (!inputJobId.trim()) return;
    setParentJobId(inputJobId.trim());
    setIsPolling(true);
  };

  const handleStop = () => setIsPolling(false);

  const handleResume = () => {
    if (parentJobId) setIsPolling(true);
  };

  const copyToClipboard = (text) => navigator.clipboard.writeText(text);

  // Compute batch status counts from statuses object
  const batchCounts = jobData?.statuses
    ? Object.values(jobData.statuses).reduce((acc, s) => {
        acc[s] = (acc[s] || 0) + 1;
        return acc;
      }, {})
    : {};

  const progress =
    jobData && jobData.total_batches > 0
      ? Math.round(
          ((jobData.total_batches - (jobData.total_pixels_remaining > 0 ? Object.values(jobData.statuses || {}).filter(s => s !== 'complete').length : 0)) /
            jobData.total_batches) *
            100
        )
      : 0;

  // Simpler progress: processed / (processed + remaining)
  const totalPixels = jobData
    ? (jobData.total_pixels_processed || 0) + (jobData.total_pixels_remaining || 0)
    : 0;
  const pixelProgress = totalPixels > 0
    ? Math.round(((jobData?.total_pixels_processed || 0) / totalPixels) * 100)
    : 0;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" fontWeight={700} gutterBottom>
        IsoFit Algorithm Dashboard
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Launch and monitor IsoFit batch processing jobs
      </Typography>

      {/* Controls */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle2" fontWeight={600} gutterBottom>
              Launch New Run
            </Typography>
            <Button
              variant="contained"
              startIcon={launching ? <CircularProgress size={16} color="inherit" /> : <RunIcon />}
              onClick={handleLaunch}
              disabled={launching || isPolling}
              fullWidth
            >
              {launching ? 'Launching…' : 'Launch IsoFit Run'}
            </Button>
            {launchError && (
              <Alert severity="error" sx={{ mt: 1 }} onClose={() => setLaunchError(null)}>
                {launchError}
              </Alert>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle2" fontWeight={600} gutterBottom>
              Monitor Existing Job
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                size="small"
                placeholder="Parent Job ID"
                value={inputJobId}
                onChange={e => setInputJobId(e.target.value)}
                fullWidth
                onKeyDown={e => e.key === 'Enter' && handleMonitor()}
              />
              <Button variant="outlined" onClick={handleMonitor} disabled={!inputJobId.trim()}>
                Monitor
              </Button>
            </Box>
          </Paper>
        </Grid>
      </Grid>

      {/* Active job */}
      {parentJobId && (
        <Paper sx={{ p: 2.5, mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="subtitle1" fontWeight={600}>
                Job:
              </Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {parentJobId}
              </Typography>
              <Tooltip title="Copy">
                <IconButton size="small" onClick={() => copyToClipboard(parentJobId)}>
                  <CopyIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              {isComplete && <StatusChip status="complete" />}
              {isPolling && !isComplete && <StatusChip status="running" />}
              {!isPolling && !isComplete && jobData && <StatusChip status="queued" />}

              {isPolling ? (
                <Button size="small" variant="outlined" color="error" startIcon={<StopIcon />} onClick={handleStop}>
                  Stop
                </Button>
              ) : (
                <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={handleResume}>
                  Resume
                </Button>
              )}
            </Box>
          </Box>

          {pollingError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {pollingError}
            </Alert>
          )}

          {jobData ? (
            <>
              {/* Pixel progress bar */}
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">Pixel Progress</Typography>
                  <Typography variant="body2" fontWeight={600}>{pixelProgress}%</Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={pixelProgress}
                  sx={{ height: 8, borderRadius: 4 }}
                  color={isComplete ? 'success' : 'primary'}
                />
                {lastUpdated && (
                  <Typography variant="caption" color="text.secondary">
                    Last updated: {lastUpdated.toLocaleTimeString()}
                  </Typography>
                )}
              </Box>

              {/* Metric cards */}
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid item xs={6} sm={3}>
                  <MetricCard label="Total Batches" value={jobData.total_batches} color="primary.main" />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <MetricCard label="Pixels Processed" value={jobData.total_pixels_processed?.toLocaleString()} color="success.main" />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <MetricCard label="Pixels Remaining" value={jobData.total_pixels_remaining?.toLocaleString()} color={jobData.total_pixels_remaining > 0 ? 'warning.main' : 'success.main'} />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <MetricCard label="Restarted Jobs" value={jobData.restarted_jobs?.length ?? 0} color={jobData.restarted_jobs?.length > 0 ? 'error.main' : 'text.secondary'} />
                </Grid>
              </Grid>

              {/* Batch status breakdown */}
              {Object.keys(batchCounts).length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                    Batch Status Breakdown
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {Object.entries(batchCounts).map(([status, count]) => (
                      <Chip key={status} label={`${status}: ${count}`} size="small"
                        color={status === 'complete' ? 'success' : status === 'failed' ? 'error' : 'default'} />
                    ))}
                  </Box>
                </Box>
              )}

              {/* Restart warning */}
              {jobData.restart_required && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Restart required. Some batches need to be re-queued.
                </Alert>
              )}

              {/* Failed pixel IDs */}
              {jobData.failed_jobs_pixel_ids?.length > 0 && (
                <Box>
                  <Typography variant="subtitle2" fontWeight={600} gutterBottom color="error">
                    Failed Pixel IDs ({jobData.failed_jobs_pixel_ids.length})
                  </Typography>
                  <Paper variant="outlined" sx={{ p: 1.5, maxHeight: 120, overflow: 'auto', bgcolor: 'grey.50' }}>
                    <Typography variant="caption" sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
                      {jobData.failed_jobs_pixel_ids.join(', ')}
                    </Typography>
                  </Paper>
                  <Button
                    size="small"
                    sx={{ mt: 0.5 }}
                    onClick={() => copyToClipboard(jobData.failed_jobs_pixel_ids.join(', '))}
                    startIcon={<CopyIcon fontSize="small" />}
                  >
                    Copy IDs
                  </Button>
                </Box>
              )}
            </>
          ) : (
            isPolling && (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                <CircularProgress />
              </Box>
            )
          )}
        </Paper>
      )}

      {/* Job history */}
      {history.length > 0 && (
        <Paper sx={{ p: 2.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
            <HistoryIcon fontSize="small" color="action" />
            <Typography variant="subtitle2" fontWeight={600}>Recent Jobs</Typography>
          </Box>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Job ID</TableCell>
                  <TableCell>Started</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {history.map(h => (
                  <TableRow key={h.id} hover>
                    <TableCell>
                      <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                        {h.id}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(h.startedAt).toLocaleString()}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        onClick={() => { setParentJobId(h.id); setInputJobId(h.id); setIsPolling(true); }}
                      >
                        Monitor
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}
    </Box>
  );
}