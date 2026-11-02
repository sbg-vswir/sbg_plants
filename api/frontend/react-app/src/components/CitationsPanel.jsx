import React, { useState } from 'react';
import {
  Box, Paper, Typography, Stack, IconButton, Collapse, Link, Button, Tooltip,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';

// Display labels for vswir_plants."DOI_role"; unknown roles fall back to the raw value
const ROLE_LABELS = {
  campaign_overview: 'Campaign overview',
  radiance_dataset:  'Radiance data',
  pixel_shade_mask:  'Pixel shade mask',
  plot_information:  'Plot information',
  plot_shapes:       'Plot shapes',
  plot_method:       'Plot method',
  trait_method:      'Trait method',
  trait_data:        'Trait data',
};

const doiUrl = (doi) => `https://doi.org/${doi}`;

// Short description of what a DOI row is scoped to, e.g. "nitrogen · combustion"
function scopeLabel(c) {
  const parts = [c.sensor_name, c.plot_method, c.trait, c.trait_method].filter(Boolean);
  if (Array.isArray(c.site_ids) && c.site_ids.length) {
    parts.push(`covers ${c.site_ids.length} site${c.site_ids.length === 1 ? '' : 's'}`);
  }
  return parts.join(' · ');
}

// { campaign_name: { role: [citation, ...] } }, keeping the backend's order
function groupCitations(citations) {
  const groups = {};
  for (const c of citations) {
    groups[c.campaign_name] ??= {};
    (groups[c.campaign_name][c.role] ??= []).push(c);
  }
  return groups;
}

/**
 * DOIs that apply to the current linked query results (all pages, not just
 * the one on screen). Comes from the `citations` key of the /query response.
 */
export default function CitationsPanel({ citations }) {
  const [open, setOpen]     = useState(true);
  const [copied, setCopied] = useState(false);

  if (!citations?.length) return null;

  const uniqueDois = [...new Set(citations.map((c) => c.doi))];
  const groups     = groupCitations(citations);

  const handleCopyAll = async () => {
    const lines = uniqueDois.map((doi) => {
      const withText = citations.find((c) => c.doi === doi && c.citation_text);
      return withText ? `${withText.citation_text} ${doiUrl(doi)}` : doiUrl(doi);
    });
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('[CitationsPanel] copy failed:', err);
    }
  };

  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Typography variant="subtitle2">
          Citations ({uniqueDois.length} DOI{uniqueDois.length === 1 ? '' : 's'})
        </Typography>
        <Stack direction="row" alignItems="center" spacing={0.5}>
          <Tooltip title="Copy every DOI link, one per line">
            <Button size="small" startIcon={<CopyIcon fontSize="small" />} onClick={handleCopyAll}>
              {copied ? 'Copied' : 'Copy all'}
            </Button>
          </Tooltip>
          <IconButton size="small" onClick={() => setOpen((o) => !o)}>
            {open ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
          </IconButton>
        </Stack>
      </Stack>

      <Collapse in={open}>
        <Typography variant="caption" color="text.secondary" component="p" sx={{ mb: 1 }}>
          Please cite these when using the data returned by this query.
        </Typography>
        {Object.entries(groups).map(([campaign, roles]) => (
          <Box key={campaign} sx={{ mb: 1.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{campaign}</Typography>
            {Object.entries(roles).map(([role, rows]) => (
              <Box key={role} sx={{ pl: 1, mt: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  {ROLE_LABELS[role] ?? role}
                </Typography>
                {rows.map((c, i) => {
                  const scope = scopeLabel(c);
                  return (
                    <Box key={`${c.doi}-${i}`} sx={{ pl: 1 }}>
                      <Link href={doiUrl(c.doi)} target="_blank" rel="noopener noreferrer" variant="caption">
                        {c.doi}
                      </Link>
                      {scope && (
                        <Typography variant="caption" color="text.secondary"> — {scope}</Typography>
                      )}
                      {c.citation_text && (
                        <Typography variant="caption" component="p" sx={{ pl: 1 }}>
                          {c.citation_text}
                        </Typography>
                      )}
                    </Box>
                  );
                })}
              </Box>
            ))}
          </Box>
        ))}
      </Collapse>
    </Paper>
  );
}
