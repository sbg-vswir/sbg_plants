import React, { useState } from 'react';
import {
  Box, Typography, Paper, Grid, Chip, LinearProgress,
  Alert, CircularProgress, Button, IconButton, Slider
} from '@mui/material';
import {
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  HourglassEmpty as PendingIcon,
  Warning as WarningIcon,
  ContentCopy as CopyIcon,
  PlayArrow as MonitorIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { useIsoFitPolling } from '../hooks/useIsoFitPolling';

const STATUS_CONFIG = {
  complete:    { color: 'success', label: 'Complete',    icon: <SuccessIcon fontSize="small" /> },
  failed:      { color: 'error',   label: 'Failed',      icon: <ErrorIcon fontSize="small" /> },
  partial:     { color: 'warning', label: 'Partial Fail', icon: <WarningIcon fontSize="small" /> },
  in_progress: { color: 'primary', label: 'In Progress', icon: <CircularProgress size={12} color="inherit" /> },
  submitted:   { color: 'info',    label: 'Submitted',   icon: <PendingIcon fontSize="small" /> },
  unknown:     { color: 'default', label: 'Unknown',     icon: <PendingIcon fontSize="small" /> },
  loading:     { color: 'default', label: 'Loading',     icon: <CircularProgress size={12} color="inherit" /> },
};

const POLL_MIN = 30;
const POLL_MAX = 600;
const POLL_DEFAULT = 60;

function StatusChip({ status }) {
  const { color, label, icon } = STATUS_CONFIG[status] ?? STATUS_CONFIG.unknown;
  return <Chip label={label} color={color} size="small" icon={icon} />;
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

export default function IsoFitStatus({ parentJobId, isPolling, onStopPolling, onStartPolling, onClose }) {
  const [pollIntervalSecs, setPollIntervalSecs] = useState(POLL_DEFAULT);

  const { jobData, pollingError, lastUpdated, isComplete, canPoll, derivedStatus } =
    useIsoFitPolling(parentJobId, isPolling, pollIntervalSecs * 1000);

  const copyToClipboard = (text) => navigator.clipboard.writeText(text);

  const totalPixels = jobData
    ? (jobData.total_pixels_processed || 0) + (jobData.total_pixels_remaining || 0)
    : 0;
  const pixelProgress = totalPixels > 0
    ? Math.round(((jobData?.total_pixels_processed || 0) / totalPixels) * 100)
    : 0;

  const batchCounts = jobData?.statuses
    ? Object.entries(jobData.statuses).reduce((acc, [s, count]) => {
        acc[s] = (acc[s] || 0) + count;
        return acc;
      }, {})
    : {};

  if (!parentJobId) return null;

  return (
    <Paper sx={{ p: 2.5, mb: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle1" fontWeight={600}>IsoFit Job:</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{parentJobId}</Typography>
          <Button size="small" onClick={() => copyToClipboard(parentJobId)} sx={{ minWidth: 0, p: 0.5 }}>
            <CopyIcon fontSize="small" />
          </Button>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <StatusChip status={derivedStatus} />
          {isPolling && (
            <Button size="small" variant="outlined" color="error" onClick={onStopPolling}>
              Stop
            </Button>
          )}
          {!isPolling && canPoll && derivedStatus !== 'failed' && derivedStatus !== 'complete' && (
            <Button size="small" variant="outlined" color="primary" startIcon={<MonitorIcon />} onClick={onStartPolling}>
              Monitor
            </Button>
          )}
          <IconButton size="small" onClick={() => { onStopPolling?.(); onClose?.(); }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>

      {/* Poll interval control */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, maxWidth: 360 }}>
        <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
          Poll every {pollIntervalSecs}s
        </Typography>
        <Slider
          value={pollIntervalSecs}
          min={POLL_MIN}
          max={POLL_MAX}
          step={30}
          onChange={(_, val) => setPollIntervalSecs(val)}
          disabled={isPolling}
          size="small"
        />
      </Box>

      {pollingError && <Alert severity="error" sx={{ mb: 2 }}>{pollingError}</Alert>}

      {!jobData && !pollingError && (
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
