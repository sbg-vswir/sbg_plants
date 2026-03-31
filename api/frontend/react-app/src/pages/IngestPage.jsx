import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Container, Typography, Paper, Button, Stack, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  CircularProgress, Alert, Collapse, IconButton, Divider, Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  Upload as UploadIcon,
  CheckCircle as ApproveIcon,
  Cancel as RejectIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import Navbar from '../components/Navbar';
import { ingestApi } from '../utils/api';
import { useIngestionPolling } from '../hooks/useIngestionPolling';

// ── File slot definitions ─────────────────────────────────────────────────────

const FILE_SLOTS = [
  {
    key:    'campaign_metadata',
    label:  'Campaign Metadata',
    accept: '.csv',
    hint:   'campaign_metadata.csv — one row per campaign + sensor combination',
  },
  {
    key:    'wavelengths',
    label:  'Wavelengths',
    accept: '.csv',
    hint:   'wavelengths.csv — one row per band, ordered by band index',
  },
  {
    key:    'granule_metadata',
    label:  'Granule Metadata',
    accept: '.csv',
    hint:   'granule_metadata.csv — one row per granule',
  },
  {
    key:    'plots',
    label:  'Plots',
    accept: '.geojson,.json',
    hint:   'plots.geojson — FeatureCollection of plot-granule intersection polygons (EPSG:4326)',
  },
  {
    key:    'traits',
    label:  'Traits',
    accept: '.csv',
    hint:   'traits.csv — one row per trait measurement',
  },
  {
    key:    'spectra',
    label:  'Spectra',
    accept: '.csv',
    hint:   'spectra.csv — one row per pixel with positional band columns (0, 1, 2 …)',
  },
];

// ── Status chip config ────────────────────────────────────────────────────────

const STATUS_CHIP = {
  PENDING:      { color: 'default',  label: 'Pending' },
  QAQC_RUNNING: { color: 'info',     label: 'QAQC Running' },
  QAQC_PASS:    { color: 'success',  label: 'QAQC Pass' },
  QAQC_FAIL:    { color: 'error',    label: 'QAQC Fail' },
  PROMOTED:     { color: 'success',  label: 'Promoted' },
  REJECTED:     { color: 'default',  label: 'Rejected' },
};

// ── QAQC report sub-component ─────────────────────────────────────────────────

function QaqcReport({ report }) {
  if (!report || Object.keys(report).length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
        No QAQC report available yet.
      </Typography>
    );
  }

  return (
    <Box sx={{ p: 2 }}>
      {Object.entries(report).map(([file, result]) => (
        <Box key={file} sx={{ mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            {file}
            {result.row_count != null && (
              <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                {result.row_count.toLocaleString()} rows
              </Typography>
            )}
          </Typography>

          {result.errors?.length > 0 && (
            <Box sx={{ mb: 0.5 }}>
              {result.errors.map((e, i) => (
                <Alert key={i} severity="error" sx={{ py: 0, mb: 0.5 }}>
                  {e}
                </Alert>
              ))}
            </Box>
          )}

          {result.warnings?.length > 0 && (
            <Box sx={{ mb: 0.5 }}>
              {result.warnings.map((w, i) => (
                <Alert key={i} severity="warning" sx={{ py: 0, mb: 0.5 }}>
                  {w}
                </Alert>
              ))}
            </Box>
          )}

          {(!result.errors?.length && !result.warnings?.length) && (
            <Alert severity="success" sx={{ py: 0 }}>All checks passed</Alert>
          )}
        </Box>
      ))}
    </Box>
  );
}

// ── Batch row sub-component ───────────────────────────────────────────────────

function BatchRow({ batch, onApprove, onReject }) {
  const [expanded, setExpanded] = useState(batch.status === 'QAQC_FAIL');
  const chip = STATUS_CHIP[batch.status] ?? { color: 'default', label: batch.status };
  const isActive = batch.status === 'PENDING' || batch.status === 'QAQC_RUNNING';

  return (
    <>
      <TableRow hover>
        <TableCell sx={{ fontFamily: 'monospace', fontSize: 12 }}>
          {batch.batch_id.slice(0, 8)}…
        </TableCell>
        <TableCell>{batch.uploaded_by}</TableCell>
        <TableCell>{new Date(batch.uploaded_at).toLocaleString()}</TableCell>
        <TableCell>
          <Stack direction="row" spacing={0.5} alignItems="center">
            <Chip label={chip.label} color={chip.color} size="small" />
            {isActive && <CircularProgress size={14} thickness={5} />}
          </Stack>
        </TableCell>
        <TableCell>
          <Stack direction="row" spacing={0.5}>
            {batch.status === 'QAQC_PASS' && (
              <>
                <Tooltip title="Approve — promote to production">
                  <Button
                    size="small"
                    variant="contained"
                    color="success"
                    startIcon={<ApproveIcon />}
                    onClick={() => onApprove(batch.batch_id)}
                    sx={{ textTransform: 'none' }}
                  >
                    Approve
                  </Button>
                </Tooltip>
                <Tooltip title="Reject — discard staging data">
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    startIcon={<RejectIcon />}
                    onClick={() => onReject(batch.batch_id)}
                    sx={{ textTransform: 'none' }}
                  >
                    Reject
                  </Button>
                </Tooltip>
              </>
            )}
            <IconButton size="small" onClick={() => setExpanded(e => !e)}>
              {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
            </IconButton>
          </Stack>
        </TableCell>
      </TableRow>

      {/* QAQC report expand */}
      <TableRow>
        <TableCell colSpan={5} sx={{ p: 0, borderBottom: expanded ? undefined : 'none' }}>
          <Collapse in={expanded} unmountOnExit>
            <Box sx={{ bgcolor: 'grey.50', borderTop: '1px solid', borderColor: 'divider' }}>
              <Typography variant="caption" color="text.secondary" sx={{ px: 2, pt: 1.5, display: 'block' }}>
                Files: {batch.files?.join(', ') ?? '—'}
              </Typography>
              <Divider sx={{ mt: 1 }} />
              <QaqcReport report={batch.qaqc_report} />
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function IngestPage() {
  const [files, setFiles]         = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [submitSuccess, setSubmitSuccess] = useState('');

  const [batches, setBatches]     = useState([]);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [batchError, setBatchError] = useState('');
  const [actionError, setActionError] = useState('');

  // Update a single batch in state when polling gets a new status
  const handleBatchUpdate = useCallback((updated) => {
    setBatches(prev => prev.map(b => b.batch_id === updated.batch_id ? updated : b));
  }, []);

  useIngestionPolling(batches, handleBatchUpdate);

  useEffect(() => { loadBatches(); }, []);

  async function loadBatches() {
    setLoadingBatches(true);
    setBatchError('');
    try {
      const data = await ingestApi.listBatches();
      setBatches(data);
    } catch (err) {
      setBatchError(err.message);
    } finally {
      setLoadingBatches(false);
    }
  }

  function handleFileChange(key, e) {
    const file = e.target.files[0];
    if (file) setFiles(prev => ({ ...prev, [key]: file }));
  }

  const allFilesSelected = FILE_SLOTS.every(s => files[s.key]);

  async function handleSubmit() {
    setSubmitting(true);
    setSubmitError('');
    setSubmitSuccess('');
    try {
      const result = await ingestApi.submitBatch(files);
      setSubmitSuccess(`Batch submitted — ID: ${result.batch_id}`);
      setFiles({});
      // Reset file inputs
      FILE_SLOTS.forEach(s => {
        const el = document.getElementById(`file-input-${s.key}`);
        if (el) el.value = '';
      });
      // Prepend new batch as PENDING and start polling
      setBatches(prev => [{
        batch_id:    result.batch_id,
        status:      'PENDING',
        uploaded_by: result.uploaded_by ?? '—',
        uploaded_at: result.uploaded_at ?? new Date().toISOString(),
        files:       FILE_SLOTS.map(s => s.key),
        qaqc_report: null,
      }, ...prev]);
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleApprove(batchId) {
    if (!window.confirm('Approve this batch and promote to production?')) return;
    setActionError('');
    try {
      const updated = await ingestApi.approveBatch(batchId);
      setBatches(prev => prev.map(b => b.batch_id === batchId ? { ...b, ...updated } : b));
    } catch (err) {
      setActionError(err.message);
    }
  }

  async function handleReject(batchId) {
    if (!window.confirm('Reject this batch? Staging data will be discarded.')) return;
    setActionError('');
    try {
      const updated = await ingestApi.rejectBatch(batchId);
      setBatches(prev => prev.map(b => b.batch_id === batchId ? { ...b, ...updated } : b));
    } catch (err) {
      setActionError(err.message);
    }
  }

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Navbar />
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <Stack direction={{ xs: 'column', lg: 'row' }} spacing={4} alignItems="flex-start">

          {/* ── Upload panel ───────────────────────────────────────────── */}
          <Box component={Paper} variant="outlined" sx={{ p: 3, width: { xs: '100%', lg: 380 }, flexShrink: 0 }}>
            <Typography variant="h6" sx={{ mb: 0.5 }}>Submit Ingestion Bundle</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              All 6 files are required. Files are validated asynchronously — you can track progress in the batch list.
            </Typography>

            {submitError   && <Alert severity="error"   sx={{ mb: 2 }}>{submitError}</Alert>}
            {submitSuccess && <Alert severity="success" sx={{ mb: 2 }}>{submitSuccess}</Alert>}

            <Stack spacing={2}>
              {FILE_SLOTS.map(slot => (
                <Box key={slot.key}>
                  <Typography variant="body2" fontWeight={500} sx={{ mb: 0.5 }}>
                    {slot.label} <Typography component="span" color="error">*</Typography>
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                    {slot.hint}
                  </Typography>
                  <input
                    id={`file-input-${slot.key}`}
                    type="file"
                    accept={slot.accept}
                    onChange={e => handleFileChange(slot.key, e)}
                    style={{ display: 'block', width: '100%' }}
                  />
                  {files[slot.key] && (
                    <Chip
                      label={files[slot.key].name}
                      size="small"
                      color="primary"
                      variant="outlined"
                      sx={{ mt: 0.5 }}
                    />
                  )}
                </Box>
              ))}

              <Divider />

              <Button
                variant="contained"
                startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : <UploadIcon />}
                onClick={handleSubmit}
                disabled={!allFilesSelected || submitting}
                fullWidth
              >
                {submitting ? 'Uploading…' : 'Submit Bundle'}
              </Button>
            </Stack>
          </Box>

          {/* ── Batch list ─────────────────────────────────────────────── */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
              <Typography variant="h6">Ingestion Batches</Typography>
              <Tooltip title="Refresh">
                <IconButton onClick={loadBatches} disabled={loadingBatches}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
            </Stack>

            {batchError   && <Alert severity="error"   sx={{ mb: 2 }}>{batchError}</Alert>}
            {actionError  && <Alert severity="error"   sx={{ mb: 2 }}>{actionError}</Alert>}

            {loadingBatches && <LinearProgress sx={{ mb: 2 }} />}

            {!loadingBatches && batches.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No batches submitted yet.
              </Typography>
            ) : (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: 'grey.50' }}>
                      <TableCell><strong>Batch ID</strong></TableCell>
                      <TableCell><strong>Submitted By</strong></TableCell>
                      <TableCell><strong>Submitted At</strong></TableCell>
                      <TableCell><strong>Status</strong></TableCell>
                      <TableCell><strong>Actions</strong></TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {batches.map(batch => (
                      <BatchRow
                        key={batch.batch_id}
                        batch={batch}
                        onApprove={handleApprove}
                        onReject={handleReject}
                      />
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>

        </Stack>
      </Container>
    </Box>
  );
}

export default IngestPage;
