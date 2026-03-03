import React from 'react';
import { Paper, Typography, Button, Link, Box, Chip } from '@mui/material';
import { Download as DownloadIcon, HourglassEmpty, CheckCircle, PlayArrow } from '@mui/icons-material';

const getStatusConfig = (status) => {
  switch (status) {
    case 'complete':
      return { color: '#e8f5e9', borderColor: '#4caf50', icon: <CheckCircle sx={{ color: '#4caf50', mr: 1 }} />, label: 'Complete', chipColor: 'success' };
    case 'running':
      return { color: '#fff3e0', borderColor: '#ff9800', icon: <PlayArrow sx={{ color: '#ff9800', mr: 1 }} />, label: 'Running', chipColor: 'warning' };
    case 'queued':
    default:
      return { color: '#e3f2fd', borderColor: '#1976d2', icon: <HourglassEmpty sx={{ color: '#1976d2', mr: 1 }} />, label: 'Queued', chipColor: 'info' };
  }
};

function JobStatus({ jobsBySensor, sensorStatuses }) {
  if (!jobsBySensor || Object.keys(jobsBySensor).length === 0) return null;

  return (
    <Box>
      {Object.entries(jobsBySensor).map(([sensorKey, jobId]) => {
        const state = sensorStatuses[sensorKey] ?? { status: 'queued', rowsProcessed: 0 };
        const statusConfig = getStatusConfig(state.status); // extract your existing switch to a standalone fn

        return (
          <Paper
            key={sensorKey}
            elevation={1}
            sx={{ p: 2, mb: 2, bgcolor: statusConfig.color, borderLeft: `4px solid ${statusConfig.borderColor}` }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              {statusConfig.icon}
              <Typography variant="h6" sx={{ mr: 2 }}>{sensorKey}</Typography>
              <Chip label={statusConfig.label} color={statusConfig.chipColor} size="small" />
            </Box>

            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              <strong>Job ID:</strong> {jobId}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              <strong>Rows processed:</strong> {state.rowsProcessed.toLocaleString()}
            </Typography>

            {state.error && (
              <Typography variant="body2" color="error">{state.error}</Typography>
            )}

            {state.downloadUrl && state.status === 'complete' && (
              <Button
                component={Link}
                href={state.downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                variant="contained"
                color="success"
                size="small"
                startIcon={<DownloadIcon />}
                sx={{ mt: 1 }}
              >
                Download Spectra Data
              </Button>
            )}
          </Paper>
        );
      })}
    </Box>
  );
}

export default JobStatus;