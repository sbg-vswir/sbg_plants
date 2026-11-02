import React, { useState, useRef } from 'react';
import {
  Box, Typography, Button, Stack, Chip, Alert, CircularProgress, useTheme, useMediaQuery,
} from '@mui/material';
import { Replay as RecheckIcon } from '@mui/icons-material';
import { ingestApi } from '../utils/api';

const DEFAULT_FILE_SLOTS = [
  { key: 'campaign_metadata', label: 'Campaign Metadata',  accept: '.csv' },
  { key: 'wavelengths',       label: 'Wavelengths',         accept: '.csv' },
  { key: 'granule_metadata',  label: 'Granule Metadata',   accept: '.csv' },
  { key: 'plots',             label: 'Plots',               accept: '.geojson,.json' },
  { key: 'traits',            label: 'Traits',              accept: '.csv' },
  { key: 'spectra',           label: 'Spectra',             accept: '.csv' },
  { key: 'doi',               label: 'DOIs',                accept: '.csv' },
];

export default function ResubmitPanel({ batchId, fileSlots, failingFiles, onReplaced, onRecheck }) {
  const theme   = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
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
              <Stack direction={isMobile ? 'column' : 'row'} spacing={1} alignItems={isMobile ? 'flex-start' : 'center'}>
                <Typography
                  variant="body2"
                  sx={{ minWidth: isMobile ? 'unset' : 160, fontWeight: hasFail ? 600 : 400, color: hasFail ? 'error.main' : 'text.secondary' }}
                >
                  {slotDef.label}{hasFail && ' *'}
                </Typography>
                <input
                  ref={el => { inputRefs.current[slot] = el; }}
                  type="file"
                  accept={slotDef.accept}
                  onChange={e => handleFileChange(slot, e)}
                  style={{ flex: isMobile ? 'unset' : 1, width: isMobile ? '100%' : undefined }}
                />
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => handleReplace(slot)}
                  disabled={!replacements[slot] || replacing[slot]}
                  sx={{ textTransform: 'none', minWidth: 80, alignSelf: isMobile ? 'flex-start' : 'auto' }}
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
