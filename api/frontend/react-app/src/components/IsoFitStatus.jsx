import React from 'react';
import {
  Box, Typography, Paper, Grid, Chip, LinearProgress,
  Alert, CircularProgress, Button
} from '@mui/material';
import {
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  HourglassEmpty as PendingIcon,
  ContentCopy as CopyIcon
} from '@mui/icons-material';
import { useIsoFitPolling } from '../hooks/useIsoFitPolling';

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
    <Paper elevation={1} sx={{ p: 2, textAlign: 'center', borderTop: 3, borderColor: color || 'primary.main' }}>
      <Typography variant="h4" fontWeight={700} color={color || 'primary.main'}>
        {value ?? '—'}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        {label}
      </Typography>
    </Paper>
  );
}

export default function IsoFitStatus({ parentJobId, isPolling, onStopPolling }) {
  const { jobData, pollingError, lastUpdated, isComplete } = useIsoFitPolling(parentJobId, isPolling);

  const copyToClipboard = (text) => navigator.clipboard.writeText(text);

  const totalPixels = jobData
    ? (jobData.total_pixels_processed || 0) + (jobData.total_pixels_remaining || 0)
    : 0;
  const pixelProgress = totalPixels > 0
    ? Math.round(((jobData?.total_pixels_processed || 0) / totalPixels) * 100)
    : 0;

  const batchCounts = jobData?.statuses
    ? Object.values(jobData.statuses).reduce((acc, s) => {
        acc[s] = (acc[s] || 0) + 1;
        return acc;
      }, {})
    : {};

  if (!parentJobId) return null;

  return (
    <Paper sx={{ p: 2.5, mb: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle1" fontWeight={600}>IsoFit Job:</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{parentJobId}</Typography>
          <Button size="small" onClick={() => copyToClipboard(parentJobId)} sx={{ minWidth: 0, p: 0.5 }}>
            <CopyIcon fontSize="small" />
          </Button>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {isComplete && <StatusChip status="complete" />}
          {isPolling && !isComplete && <StatusChip status="running" />}
          {!isPolling && !isComplete && jobData && <StatusChip status="queued" />}
          {isPolling && (
            <Button size="small" variant="outlined" color="error" onClick={onStopPolling}>
              Stop
            </Button>
          )}
        </Box>
      </Box>

      {pollingError && <Alert severity="error" sx={{ mb: 2 }}>{pollingError}</Alert>}

      {!jobData && isPolling && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress />
        </Box>
      )}

      {jobData && (
        <>
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

          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={6} sm={3}>
              <MetricCard label="Total Batches" value={jobData.total_batches} color="primary.main" />
            </Grid>
            <Grid item xs={6} sm={3}>
              <MetricCard label="Pixels Processed" value={jobData.total_pixels_processed?.toLocaleString()} color="success.main" />
            </Grid>
            <Grid item xs={6} sm={3}>
              <MetricCard
                label="Pixels Remaining"
                value={jobData.total_pixels_remaining?.toLocaleString()}
                color={jobData.total_pixels_remaining > 0 ? 'warning.main' : 'success.main'}
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <MetricCard
                label="Restarted Jobs"
                value={jobData.restarted_jobs?.length ?? 0}
                color={jobData.restarted_jobs?.length > 0 ? 'error.main' : 'text.secondary'}
              />
            </Grid>
          </Grid>

          {Object.keys(batchCounts).length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" fontWeight={600} gutterBottom>Batch Status Breakdown</Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {Object.entries(batchCounts).map(([status, count]) => (
                  <Chip
                    key={status}
                    label={`${status}: ${count}`}
                    size="small"
                    color={status === 'complete' ? 'success' : status === 'failed' ? 'error' : 'default'}
                  />
                ))}
              </Box>
            </Box>
          )}

          {jobData.restart_required && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Restart required. Some batches need to be re-queued.
            </Alert>
          )}

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
                startIcon={<CopyIcon fontSize="small" />}
                onClick={() => copyToClipboard(jobData.failed_jobs_pixel_ids.join(', '))}
              >
                Copy IDs
              </Button>
            </Box>
          )}
        </>
      )}
    </Paper>
  );
}