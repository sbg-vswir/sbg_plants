import React from 'react';
import { Box, Typography, Alert, Chip, CircularProgress } from '@mui/material';

// ── Message normalisation helpers ─────────────────────────────────────────────

function enumColumn(msg) {
  const m = msg.match(/is not a valid value for '([^']+)'/);
  return m ? m[1] : null;
}

function normaliseMessage(msg) {
  const col = enumColumn(msg);
  if (col) return `is not a valid value for '${col}'`;

  // Messages that carry meaningful context — pass through unchanged so each
  // unique value groups separately and the value remains visible.
  if (msg.includes('already exists in database')) return msg;
  if (msg.includes('traits.csv') || msg.includes('plots.geojson')) return msg;

  // Everything else: strip variable tuple/kwarg data so messages differing only
  // in data values collapse into the same group.
  return msg
    .replace(/\([^)]*\)/g, '(…)')
    .replace(/'[^']*'/g, "'…'");
}

function buildRanges(sorted) {
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
  return ranges;
}

function compressErrors(items) {
  if (!items?.length) return [];

  // ── Pass 1: group by normalised message + column ──────────────────────────
  const groups = new Map();
  for (const item of items) {
    const msg = typeof item === 'string' ? item : item.message;
    const col = typeof item === 'object' ? (item.column || null) : null;
    const row = typeof item === 'object' ? item.row : null;
    const key = `${col}||${normaliseMessage(msg)}`;
    if (!groups.has(key)) {
      groups.set(key, { message: normaliseMessage(msg), column: col, rows: [], count: 0, badValues: new Set() });
    }
    const g = groups.get(key);
    g.count++;
    if (row != null) g.rows.push(row);
    const enumMatch = msg.match(/^'([^']+)' is not a valid value/);
    if (enumMatch) g.badValues.add(enumMatch[1]);
  }

  // ── Pass 2: merge simple "already exists" groups per column ───────────────
  // Only merges 'value' already exists / (tuple) already exists patterns —
  // not descriptive plot messages which carry context beyond the value.
  const isSimpleAlreadyExists = (msg) =>
    msg.includes('already exists in database') &&
    (msg.startsWith("'") || (msg.startsWith('(') && !msg.includes('campaign_name=')));

  const alreadyExistsByCol = new Map();
  for (const g of groups.values()) {
    if (!isSimpleAlreadyExists(g.message)) continue;
    if (!alreadyExistsByCol.has(g.column)) alreadyExistsByCol.set(g.column, []);
    alreadyExistsByCol.get(g.column).push(g);
  }
  for (const [col, colGroups] of alreadyExistsByCol) {
    if (colGroups.length <= 1) continue;
    const totalCount = colGroups.reduce((s, g) => s + g.count, 0);
    const allRows    = colGroups.flatMap(g => g.rows);
    groups.set(`${col}||__already_exists_merged__`, {
      message:   `${totalCount} ${totalCount === 1 ? 'value' : 'values'} already exist in database`,
      column:    col,
      rows:      allRows,
      count:     totalCount,
      badValues: new Set(),
      merged:    true,
    });
    for (const g of colGroups) {
      for (const [k, v] of groups) { if (v === g) { groups.delete(k); break; } }
    }
  }

  // ── Pass 3: merge plot-granule intersection "already exists" ──────────────
  const INTERSECT_EXISTS_RE = /^plot-granule intersection \(.+\) already exists in database$/;
  const intersectExists = [...groups.entries()].filter(([, g]) => INTERSECT_EXISTS_RE.test(g.message));
  if (intersectExists.length > 1) {
    groups.set('__intersect_exists__', {
      message:   `${intersectExists.length} plot-granule intersections already exist in database`,
      column:    null,
      rows:      intersectExists.flatMap(([, g]) => g.rows),
      count:     0,
      badValues: new Set(),
    });
    for (const [k] of intersectExists) groups.delete(k);
  }

  // ── Pass 4: merge plot "already exists" errors ────────────────────────────
  const PLOT_EXISTS_RE = /^\(campaign_name='[^']*', plot_name='[^']*'\) already exists in database/;
  const plotExists = [...groups.entries()].filter(([, g]) => PLOT_EXISTS_RE.test(g.message));
  if (plotExists.length > 1) {
    groups.set('__plot_exists__', {
      message:   `${plotExists.length} plots already exist in database`,
      column:    null,
      rows:      [],
      count:     0,
      badValues: new Set(),
    });
    for (const [k] of plotExists) groups.delete(k);
  }

  // ── Pass 5: merge cross-file plot warnings, listing plot names ────────────
  const CROSS_FILE_RE = /^plot '([^']+)' \(campaign '[^']*'\) (.+)$/;
  const crossFileByTemplate = new Map();
  for (const [k, g] of groups) {
    const m = g.message.match(CROSS_FILE_RE);
    if (!m) continue;
    const template = m[2];
    if (!crossFileByTemplate.has(template)) crossFileByTemplate.set(template, []);
    crossFileByTemplate.get(template).push([k, g]);
  }
  for (const [template, entries] of crossFileByTemplate) {
    if (entries.length <= 1) continue;
    const plotNames = entries.map(([, g]) => {
      const m = g.message.match(CROSS_FILE_RE);
      return m ? m[1] : '?';
    });
    groups.set(`__cross_file__||${template}`, {
      message:   `plots ${plotNames.join(', ')}: ${template}`,
      column:    null,
      rows:      [],
      count:     0,
      badValues: new Set(),
    });
    for (const [k] of entries) groups.delete(k);
  }

  // ── Render pass: convert groups to display objects ────────────────────────
  return Array.from(groups.values()).map(({ message, column, rows, count, badValues }) => {
    const prefix = column ? `${column}: ` : '';

    // Enum group — rewrite label to list distinct bad values
    if (message.startsWith("is not a valid value for '")) {
      const label = badValues.size === 1
        ? `invalid value: '${[...badValues][0]}'`
        : `${badValues.size} invalid values: ${[...badValues].map(v => `'${v}'`).join(', ')}`;
      if (rows.length === 0) return { label, prefix, count };
      const sorted   = [...new Set(rows)].sort((a, b) => a - b);
      const rowLabel = rows.length === 1 ? `Row ${buildRanges(sorted)[0]}` : `Rows ${buildRanges(sorted).join(', ')}`;
      return { label, prefix, rowLabel, count };
    }

    // Merged "already exists" count — no row range, no badge
    if (message.match(/^\d+ values? already exist/)) {
      return { label: message, prefix, count: 0 };
    }

    if (rows.length === 0) return { label: message, prefix, count };

    const sorted   = [...new Set(rows)].sort((a, b) => a - b);
    const rowLabel = rows.length === 1
      ? `Row ${buildRanges(sorted)[0]}`
      : `Rows ${buildRanges(sorted).join(', ')}`;

    return { label: message, prefix, rowLabel, count };
  });
}

// ── Summary chip config ───────────────────────────────────────────────────────

const SUMMARY_LABELS = [
  { key: 'campaigns',           label: 'campaign' },
  { key: 'sensors',             label: 'sensor' },
  { key: 'granules',            label: 'granule' },
  { key: 'plots',               label: 'plot' },
  { key: 'plot_granule_combos', label: 'plot-granule' },
  { key: 'samples',             label: 'sample' },
  { key: 'traits',              label: 'trait' },
  { key: 'pixels',              label: 'pixel' },
];

// ── Alert row renderer ────────────────────────────────────────────────────────

function AlertRow({ item, severity }) {
  return (
    <Alert severity={severity} sx={{ py: 0, mb: 0.5 }}>
      {item.rowLabel
        ? <><span style={{ fontWeight: 600, marginRight: 6 }}>{item.rowLabel}:</span>{item.prefix}{item.label}</>
        : <><span style={{ fontWeight: 600 }}>{item.prefix}{item.label}</span>{item.count > 1 && <span style={{ marginLeft: 6, opacity: 0.7 }}>({item.count} occurrences)</span>}</>
      }
    </Alert>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function QaqcReport({ report, loading }) {
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

  const internalErrors = Object.entries(report).filter(([k]) => k.startsWith('_') && k !== '_summary');
  const fileResults    = Object.entries(report).filter(([k]) => !k.startsWith('_'));
  const summary        = report._summary;

  return (
    <Box sx={{ p: 2 }}>
      {/* Bundle summary counts */}
      {summary && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
          {SUMMARY_LABELS.map(({ key, label }) => {
            const val = summary[key];
            if (val == null) return null;
            return (
              <Chip
                key={key}
                size="small"
                label={`${val.toLocaleString()} ${label}${val !== 1 ? 's' : ''}`}
                variant="outlined"
              />
            );
          })}
        </Box>
      )}

      {/* System / parse errors */}
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
                <AlertRow key={i} item={e} severity="error" />
              ))}
            </Box>
          )}

          {result.warnings?.length > 0 && (
            <Box sx={{ mb: 0.5 }}>
              {compressErrors(result.warnings).map((w, i) => (
                <AlertRow key={i} item={w} severity="warning" />
              ))}
            </Box>
          )}

          {result.not_provided ? (
            <Alert severity="info" sx={{ py: 0 }}>Not provided in this bundle</Alert>
          ) : (!result.errors?.length && !result.warnings?.length) && (
            <Alert severity="success" sx={{ py: 0 }}>All checks passed</Alert>
          )}
        </Box>
      ))}
    </Box>
  );
}
