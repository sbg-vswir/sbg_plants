import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Button, Stack, Chip, Collapse, Divider,
  TableRow, TableCell, IconButton, Tooltip, CircularProgress,
} from '@mui/material';
import {
  CheckCircle as ApproveIcon,
  Cancel as RejectIcon,
  DeleteForever as DeleteIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import { ingestApi } from '../utils/api';
import QaqcReport from './QaqcReport';
import ResubmitPanel from './ResubmitPanel';

export const STATUS_CHIP = {
  PENDING:      { color: 'default',  label: 'Pending' },
  QAQC_RUNNING: { color: 'info',     label: 'QAQC Running' },
  QAQC_PASS:    { color: 'success',  label: 'QAQC Pass' },
  QAQC_FAIL:    { color: 'error',    label: 'QAQC Fail' },
  PROMOTED:     { color: 'success',  label: 'Promoted' },
  REJECTED:     { color: 'default',  label: 'Rejected' },
};

// Mirrors NON_DELETABLE_STATUSES in ingest_trigger/app/main.py — PENDING/
// QAQC_RUNNING (avoids a race with the fire-and-forget QAQC lambda) and
// PROMOTED (keep the audit trail of what made it to production).
const DELETABLE_STATUSES = new Set(['QAQC_PASS', 'QAQC_FAIL', 'REJECTED']);

export default function BatchRow({ batch, fileSlots, onApprove, onReject, onDelete, onBatchUpdate }) {
  const [expanded, setExpanded]           = useState(false);
  const [replacedSlots, setReplacedSlots] = useState(new Set());
  const [fullReport, setFullReport]       = useState(null);
  const [rechecking, setRechecking]       = useState(false);

  const chip     = STATUS_CHIP[batch.status] ?? { color: 'default', label: batch.status };
  const isActive = batch.status === 'PENDING' || batch.status === 'QAQC_RUNNING';
  const isFail   = batch.status === 'QAQC_FAIL';

  // Clear the rechecking flag once the QAQC run completes
  useEffect(() => {
    if (rechecking && !isActive) setRechecking(false);
  }, [batch.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch full S3 report when a QAQC_FAIL row is expanded
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
  }, [expanded, batch.status, batch.qaqc_report_s3_key]); // eslint-disable-line react-hooks/exhaustive-deps

  // Only show a report for terminal states that actually have one.
  // Never show a stale report while active or rechecking.
  const displayReport = (!rechecking && isFail)
    ? (fullReport || batch.qaqc_report)
    : null;

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
    onBatchUpdate({ ...batch, status: 'PENDING', qaqc_report: null });
  }

  return (
    <>
      <TableRow hover>
        <TableCell>
          <Typography variant="body2">{batch.name || 'Unnamed batch'}</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
            {batch.batch_id.slice(0, 8)}…
          </Typography>
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
            {DELETABLE_STATUSES.has(batch.status) && (
              <Tooltip title="Delete — permanently removes files and this record">
                <IconButton
                  size="small"
                  color="error"
                  onClick={() => onDelete(batch.batch_id, batch.name)}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Stack>
        </TableCell>
        <TableCell>
          <Stack direction="row" spacing={0.5} alignItems="center">
            <Chip label={chip.label} color={chip.color} size="small" />
            {isActive && <CircularProgress size={14} thickness={5} />}
          </Stack>
        </TableCell>
        <TableCell>{batch.uploaded_by}</TableCell>
        <TableCell>{new Date(batch.uploaded_at).toLocaleString()}</TableCell>
      </TableRow>

      {/* Expandable QAQC report + resubmit panel */}
      <TableRow>
        <TableCell colSpan={5} sx={{ p: 0, borderBottom: expanded ? undefined : 'none', minWidth: { xs: 320, sm: 'unset' } }}>
          <Collapse in={expanded} unmountOnExit>
            <Box sx={{ bgcolor: 'grey.50', borderTop: '1px solid', borderColor: 'divider' }}>
              <Typography variant="caption" color="text.secondary" sx={{ px: 2, pt: 1.5, display: 'block' }}>
                Files: {batch.files?.join(', ') ?? '—'}
              </Typography>
              <Divider sx={{ mt: 1 }} />
              <QaqcReport
                report={displayReport}
                loading={isFail && expanded && !fullReport && !!(batch.qaqc_report_presigned_url || batch.qaqc_report_s3_key)}
              />
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
