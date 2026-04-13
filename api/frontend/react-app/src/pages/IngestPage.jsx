import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  Replay as RecheckIcon,
} from '@mui/icons-material';
import Navbar from '../components/Navbar';
import { ingestApi } from '../utils/api';
import { useIngestionPolling } from '../hooks/useIngestionPolling';

// ── File slot definitions ─────────────────────────────────────────────────────
// Loaded dynamically from GET /ingest/config on page mount.
// Fallback to hardcoded defaults if the config endpoint fails.

const DEFAULT_FILE_SLOTS = [
  { key: 'campaign_metadata', label: 'Campaign Metadata',  accept: '.csv',          hint: 'campaign_metadata.csv — one row per campaign + sensor combination' },
  { key: 'wavelengths',       label: 'Wavelengths',         accept: '.csv',          hint: 'wavelengths.csv — one row per band, ordered by band index' },
  { key: 'granule_metadata',  label: 'Granule Metadata',   accept: '.csv',          hint: 'granule_metadata.csv — one row per granule' },
  { key: 'plots',             label: 'Plots',               accept: '.geojson,.json', hint: 'plots.geojson — FeatureCollection of plot-granule intersection polygons (EPSG:4326)' },
  { key: 'traits',            label: 'Traits',              accept: '.csv',          hint: 'traits.csv — one row per trait measurement' },
  { key: 'spectra',           label: 'Spectra',             accept: '.csv',          hint: 'spectra.csv — one row per pixel with positional band columns (0, 1, 2 …)' },
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

/**
 * Group a list of error/warning objects by message+column, collapsing row numbers
 * into compact ranges. e.g. rows [1,2,3,5,6,10] → "Rows 1-3, 5-6, 10"
 */
function compressErrors(items) {
  if (!items?.length) return [];

  // Group by message + column
  const groups = new Map();
  for (const item of items) {
    const msg = typeof item === 'string' ? item : item.message;
    const col = typeof item === 'object' ? (item.column || null) : null;
    const row = typeof item === 'object' ? item.row : null;
    const key = `${col}||${msg}`;
    if (!groups.has(key)) groups.set(key, { message: msg, column: col, rows: [] });
    if (row != null) groups.get(key).rows.push(row);
  }

  return Array.from(groups.values()).map(({ message, column, rows }) => {
    const prefix = column ? `${column}: ` : '';
    if (rows.length === 0) return { label: message, prefix };

    // Sort and build ranges
    const sorted = [...new Set(rows)].sort((a, b) => a - b);
    const ranges = [];
    let start = sorted[0], end = sorted[0];
    for (let i = 1; i < sorted.length; i++) {
      if (sorted[i] === end + 1) {
        end = sorted[i];
      } else {
        ranges.push(start === end ? `${start}` : `${start}-${end}`);
        start = end = sorted[i];
      }
    }
    ranges.push(start === end ? `${start}` : `${start}-${end}`);

    const rowLabel = rows.length === 1
      ? `Row ${ranges[0]}`
      : `Rows ${ranges.join(', ')}`;

    return { label: message, prefix, rowLabel, count: rows.length };
  });
}

function QaqcReport({ report, loading }) {
  if (loading) {
    return (
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={14} thickness={5} />
        <Typography variant="body2" color="text.secondary">Loading QAQC report…</Typography>
      </Box>
    );
  }

  if (!report || Object.keys(report).length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
        No QAQC report available yet.
      </Typography>
    );
  }

  // Separate internal error keys (_error, _parse_error) from per-file results
  const internalErrors = Object.entries(report).filter(([k]) => k.startsWith('_'));
  const fileResults    = Object.entries(report).filter(([k]) => !k.startsWith('_'));

  return (
    <Box sx={{ p: 2 }}>
      {/* Universal / system errors */}
      {internalErrors.map(([key, result]) => {
        const msg = result.error_msg
          || result.errors?.[0]?.message
          || result.errors?.[0]
          || 'An unexpected error occurred during QAQC';
        return (
          <Alert key={key} severity="error" sx={{ mb: 2 }}>
            <strong>{key === '_parse_error' ? 'File parse error' : 'QAQC system error'}:</strong> {msg}
          </Alert>
        );
      })}

      {/* Per-file results */}
      {fileResults.map(([file, result]) => (
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
              {compressErrors(result.errors).map((e, i) => (
                <Alert key={i} severity="error" sx={{ py: 0, mb: 0.5 }}>
                  {e.rowLabel
                    ? <><span style={{ fontWeight: 600, marginRight: 6 }}>{e.rowLabel}:</span>{e.prefix}{e.label}{e.count > 1 && <span style={{ marginLeft: 6, opacity: 0.7 }}>({e.count} rows)</span>}</>
                    : <span style={{ fontWeight: 600 }}>{e.prefix}{e.label}</span>
                  }
                </Alert>
              ))}
            </Box>
          )}

          {result.warnings?.length > 0 && (
            <Box sx={{ mb: 0.5 }}>
              {compressErrors(result.warnings).map((w, i) => (
                <Alert key={i} severity="warning" sx={{ py: 0, mb: 0.5 }}>
                  {w.rowLabel
                    ? <><span style={{ fontWeight: 600, marginRight: 6 }}>{w.rowLabel}:</span>{w.prefix}{w.label}{w.count > 1 && <span style={{ marginLeft: 6, opacity: 0.7 }}>({w.count} rows)</span>}</>
                    : <span style={{ fontWeight: 600 }}>{w.prefix}{w.label}</span>
                  }
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

// ── Per-slot re-upload panel (shown only on QAQC_FAIL batches) ────────────────

function ResubmitPanel({ batchId, fileSlots, failingFiles, onReplaced, onRecheck }) {
  const [replacements, setReplacements] = useState({});
  const [replacing, setReplacing]       = useState({});
  const [replaceErrors, setReplaceErrors] = useState({});
  const [rechecking, setRechecking]     = useState(false);
  const [recheckError, setRecheckError] = useState('');
  const inputRefs = useRef({});

  function handleFileChange(slot, e) {
    const file = e.target.files[0];
    if (file) setReplacements(prev => ({ ...prev, [slot]: file }));
  }

  async function handleReplace(slot) {
    const file = replacements[slot];
    if (!file) return;
    setReplacing(prev => ({ ...prev, [slot]: true }));
    setReplaceErrors(prev => ({ ...prev, [slot]: '' }));
    try {
      await ingestApi.replaceFile(batchId, slot, file);
      setReplacements(prev => { const n = { ...prev }; delete n[slot]; return n; });
      // Reset the file input
      if (inputRefs.current[slot]) inputRefs.current[slot].value = '';
      onReplaced(slot);
    } catch (err) {
      setReplaceErrors(prev => ({ ...prev, [slot]: err.message }));
    } finally {
      setReplacing(prev => ({ ...prev, [slot]: false }));
    }
  }

  async function handleRecheck() {
    setRechecking(true);
    setRecheckError('');
    try {
      await ingestApi.recheckBatch(batchId);
      onRecheck();
    } catch (err) {
      setRecheckError(err.message);
      setRechecking(false);
    }
  }

  return (
    <Box sx={{ p: 2, bgcolor: 'grey.50', borderTop: '1px solid', borderColor: 'divider' }}>
      <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
        Replace corrected files
      </Typography>

      <Stack spacing={1.5} sx={{ mb: 2 }}>
        {fileSlots.map(slot => {
          const slotDef = DEFAULT_FILE_SLOTS.find(s => s.key === slot) ?? { key: slot, label: slot, accept: '*' };
          const hasFail = failingFiles.has(slot);
          return (
            <Box key={slot}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography
                  variant="body2"
                  sx={{ minWidth: 160, fontWeight: hasFail ? 600 : 400, color: hasFail ? 'error.main' : 'text.secondary' }}
                >
                  {slotDef.label}
                  {hasFail && ' *'}
                </Typography>
                <input
                  ref={el => { inputRefs.current[slot] = el; }}
                  type="file"
                  accept={slotDef.accept}
                  onChange={e => handleFileChange(slot, e)}
                  style={{ flex: 1 }}
                />
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => handleReplace(slot)}
                  disabled={!replacements[slot] || replacing[slot]}
                  sx={{ textTransform: 'none', minWidth: 80 }}
                >
                  {replacing[slot] ? <CircularProgress size={14} /> : 'Upload'}
                </Button>
              </Stack>
              {replacements[slot] && (
                <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mt: 0.5 }}>
                  <Chip
                    label={replacements[slot].name}
                    size="small"
                    color="primary"
                    variant="outlined"
                    onDelete={() => {
                      setReplacements(prev => { const n = { ...prev }; delete n[slot]; return n; });
                      if (inputRefs.current[slot]) inputRefs.current[slot].value = '';
                    }}
                  />
                </Stack>
              )}
              {replaceErrors[slot] && (
                <Alert severity="error" sx={{ mt: 0.5, py: 0 }}>{replaceErrors[slot]}</Alert>
              )}
            </Box>
          );
        })}
      </Stack>

      {recheckError && <Alert severity="error" sx={{ mb: 1 }}>{recheckError}</Alert>}

      <Button
        variant="contained"
        startIcon={rechecking ? <CircularProgress size={16} color="inherit" /> : <RecheckIcon />}
        onClick={handleRecheck}
        disabled={rechecking}
        sx={{ textTransform: 'none' }}
      >
        {rechecking ? 'Submitting recheck…' : 'Recheck Bundle'}
      </Button>
    </Box>
  );
}

// ── Batch row sub-component ───────────────────────────────────────────────────

function BatchRow({ batch, fileSlots, onApprove, onReject, onBatchUpdate }) {
  const [expanded, setExpanded]           = useState(false);
  const [replacedSlots, setReplacedSlots] = useState(new Set());
  const [fullReport, setFullReport]       = useState(null);
  const [rechecking, setRechecking]       = useState(false);
  const chip     = STATUS_CHIP[batch.status] ?? { color: 'default', label: batch.status };
  const isActive = batch.status === 'PENDING' || batch.status === 'QAQC_RUNNING';
  const isFail   = batch.status === 'QAQC_FAIL';

  // Clear the rechecking flag once the QAQC run completes (pass or fail)
  useEffect(() => {
    if (rechecking && !isActive) {
      setRechecking(false);
    }
  }, [batch.status]);  // eslint-disable-line react-hooks/exhaustive-deps

  // When a QAQC_FAIL row is expanded, fetch the full batch record to get the
  // presigned URL (the list endpoint doesn't include it), then fetch the S3
  // report. Also re-fires when qaqc_report_s3_key changes so a new report
  // is loaded after a recheck completes.
  useEffect(() => {
    if (!expanded || !isFail) return;

    setFullReport(null);

    if (batch.qaqc_report_presigned_url) {
      fetch(batch.qaqc_report_presigned_url)
        .then(r => r.json())
        .then(data => setFullReport(data.files ?? data))
        .catch(() => {});
    } else if (batch.qaqc_report_s3_key) {
      ingestApi.getBatch(batch.batch_id)
        .then(full => {
          onBatchUpdate(full);
          if (full.qaqc_report_presigned_url) {
            return fetch(full.qaqc_report_presigned_url).then(r => r.json());
          }
        })
        .then(data => { if (data) setFullReport(data.files ?? data); })
        .catch(() => {});
    }
  }, [expanded, batch.status, batch.qaqc_report_s3_key]);  // eslint-disable-line react-hooks/exhaustive-deps

  // While a recheck is running, don't show the stale DynamoDB summary — it
  // only has pass/row_count from the previous run and will show all checks
  // passed even if the prior run had errors.
  const displayReport = rechecking ? null : (fullReport || batch.qaqc_report);

  // Derive which file slots have at least one error in the QAQC report
  const failingFiles = React.useMemo(() => {
    if (!displayReport) return new Set();
    return new Set(
      Object.entries(displayReport)
        .filter(([, result]) => result.errors?.length > 0)
        .map(([file]) => file)
    );
  }, [displayReport]);

  function handleReplaced(slot) {
    setReplacedSlots(prev => new Set([...prev, slot]));
  }

  function handleRecheck() {
    setRechecking(true);
    setFullReport(null);
    setReplacedSlots(new Set());
    setExpanded(false);
    // Optimistically update to PENDING so polling kicks in
    onBatchUpdate({ ...batch, status: 'PENDING', qaqc_report: null });
  }

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
            {isFail && (
              <Button
                size="small"
                variant="outlined"
                color="error"
                onClick={() => setExpanded(e => !e)}
                sx={{ textTransform: 'none' }}
              >
                {expanded ? 'Hide Report' : 'View Report'}
              </Button>
            )}
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
              {!isFail && (
                <IconButton size="small" onClick={() => setExpanded(e => !e)}>
                  {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                </IconButton>
              )}
            </Stack>
          </TableCell>
        </TableRow>

      {/* QAQC report + resubmit panel expand */}
      <TableRow>
        <TableCell colSpan={5} sx={{ p: 0, borderBottom: expanded ? undefined : 'none' }}>
          <Collapse in={expanded} unmountOnExit>
            <Box sx={{ bgcolor: 'grey.50', borderTop: '1px solid', borderColor: 'divider' }}>
              <Typography variant="caption" color="text.secondary" sx={{ px: 2, pt: 1.5, display: 'block' }}>
                Files: {batch.files?.join(', ') ?? '—'}
              </Typography>
              <Divider sx={{ mt: 1 }} />
              <QaqcReport report={displayReport} loading={isFail && expanded && !fullReport && !!(batch.qaqc_report_presigned_url || batch.qaqc_report_s3_key)} />

              {isFail && (
                <>
                  <Divider />
                  <ResubmitPanel
                    batchId={batch.batch_id}
                    fileSlots={fileSlots}
                    failingFiles={failingFiles}
                    onReplaced={handleReplaced}
                    onRecheck={handleRecheck}
                  />
                </>
              )}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function IngestPage() {
  const [fileSlots, setFileSlots]     = useState(DEFAULT_FILE_SLOTS);
  const [files, setFiles]             = useState({});
  const [submitting, setSubmitting]   = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [submitSuccess, setSubmitSuccess] = useState('');

  const [batches, setBatches]           = useState([]);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [batchError, setBatchError]     = useState('');
  const [actionError, setActionError]   = useState('');

  // Load file slot config from backend on mount
  useEffect(() => {
    ingestApi.getConfig()
      .then(config => {
        if (config?.file_slots) {
          const slots = Object.entries(config.file_slots).map(([key, ext]) => ({
            key,
            label:  key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
            accept: ext === '.geojson' ? '.geojson,.json' : ext,
            hint:   `${key}${ext}`,
          }));
          setFileSlots(slots);
        }
      })
      .catch(() => {
        // silently fall back to DEFAULT_FILE_SLOTS
      });
  }, []);

  // Update a single batch in state when polling or an action returns a new status
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

  const fileInputRefs = useRef({});

  function handleFileChange(key, e) {
    const file = e.target.files[0];
    if (file) setFiles(prev => ({ ...prev, [key]: file }));
  }

  function handleFileClear(key) {
    setFiles(prev => { const n = { ...prev }; delete n[key]; return n; });
    if (fileInputRefs.current[key]) fileInputRefs.current[key].value = '';
  }

  const allFilesSelected = fileSlots.every(s => files[s.key]);

  async function handleSubmit() {
    setSubmitting(true);
    setSubmitError('');
    setSubmitSuccess('');
    try {
      const result = await ingestApi.submitBatch(files);
      setSubmitSuccess(`Batch submitted — ID: ${result.batch_id}`);
      setFiles({});
      // Reset file inputs
      fileSlots.forEach(s => {
        if (fileInputRefs.current[s.key]) fileInputRefs.current[s.key].value = '';
      });
      // Prepend new batch as PENDING and start polling
      setBatches(prev => [{
        batch_id:    result.batch_id,
        status:      'PENDING',
        uploaded_by: result.uploaded_by ?? '—',
        uploaded_at: result.uploaded_at ?? new Date().toISOString(),
        files:       fileSlots.map(s => s.key),
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

  // The list of slot keys (strings) for use in ResubmitPanel
  const fileSlotKeys = fileSlots.map(s => s.key);

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
              {fileSlots.map(slot => (
                <Box key={slot.key}>
                  <Typography variant="body2" fontWeight={500} sx={{ mb: 0.5 }}>
                    {slot.label} <Typography component="span" color="error">*</Typography>
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                    {slot.hint}
                  </Typography>
                  <input
                    id={`file-input-${slot.key}`}
                    ref={el => { fileInputRefs.current[slot.key] = el; }}
                    type="file"
                    accept={slot.accept}
                    onChange={e => handleFileChange(slot.key, e)}
                    style={{ display: 'block', width: '100%' }}
                  />
                  {files[slot.key] && (
                    <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mt: 0.5 }}>
                      <Chip
                        label={files[slot.key].name}
                        size="small"
                        color="primary"
                        variant="outlined"
                        onDelete={() => handleFileClear(slot.key)}
                      />
                    </Stack>
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
                        fileSlots={fileSlotKeys}
                        onApprove={handleApprove}
                        onReject={handleReject}
                        onBatchUpdate={handleBatchUpdate}
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
