/**
 * Summarize value for display
 */
/**
 * Summarize value for display
 */
export function summarizeValue(v, n = 2) {
  if (v === null || v === undefined) {
    return '—';
  }

  // Handle BigInt
  if (typeof v === 'bigint') {
    return v.toString();
  }

  // Format ISO date strings as YYYY-MM-DD — strip time and quotes
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}(T.*)?$/.test(v)) {
    return v.slice(0, 10);
  }

  // Strip leading/trailing whitespace from strings
  if (typeof v === 'string') {
    return v.trim();
  }
  
  if (Array.isArray(v)) {
    if (v.length <= 2 * n) {
      return JSON.stringify(v, (key, value) =>
        typeof value === 'bigint' ? value.toString() : value
      );
    }
    return `[${v.slice(0, n).join(', ')}, ..., ${v.slice(-n).join(', ')}]`;
  }
  
  if (typeof v === 'object') {
    // Date objects — format as YYYY-MM-DD
    if (v instanceof Date) {
      return v.toISOString().slice(0, 10);
    }
    return JSON.stringify(v, (key, value) =>
      typeof value === 'bigint' ? value.toString() : value
    );
  }
  
  return String(v);
}
/**
 * Convert sorted values to ranges
 */
export function toRanges(sortedValues) {
  const ranges = [];
  let start = sortedValues[0];
  let prev = sortedValues[0];

  for (let i = 1; i < sortedValues.length; i++) {
    const val = sortedValues[i];
    if (val === prev + 1) {
      prev = val;
    } else {
      ranges.push([start, prev]);
      start = val;
      prev = val;
    }
  }
  ranges.push([start, prev]);
  return ranges;
}
/**
 * Parse filter values and GeoJSON
 */
export function parseFilters(filterValues, geojsonContent) {
  const filters = {};
  
  Object.keys(filterValues).forEach(key => {
    const value = filterValues[key];
    // Skip empty values: null, undefined, empty string, or empty array
    if (!value || (Array.isArray(value) && value.length === 0)) return;
    if (key === 'plot_name' || key === 'granule_id') {
      // Support comma-separated values for multi-value IN queries
      filters[key] = Array.isArray(value)
        ? value
        : value.split(',').map(p => p.trim()).filter(Boolean);
    } else if (Array.isArray(value)) {
      // Multi-select enum: pass the array directly
      filters[key] = value;
    } else if (value instanceof Date && !isNaN(value)) {
      // Format Date objects as YYYY-MM-DD — prevents JSON.stringify from
      // serializing them as full ISO timestamps (e.g. 2023-08-01T00:00:00.000Z)
      filters[key] = value.toISOString().slice(0, 10);
    } else {
      filters[key] = value;
    }
  });

  filters.geom = null;
  if (geojsonContent) {
    try {
      filters.geom = JSON.parse(geojsonContent);
    } catch (e) {
      console.error('Error parsing GeoJSON:', e);
    }
  }

  return filters;
}


export function convertToCSV(data, columnNames) {
  if (!data.length) return '';

  function formatCell(val) {
    if (val === null || val === undefined) return '';

    // Arrays → bracketed, comma-separated, **quoted** so Excel treats as one cell
    if (Array.isArray(val)) {
      return `"[` + val.join(',') + `]"`; // <-- this evaluates val, not string
    }

    // Dates → YYYY-MM-DD
    if (val instanceof Date) return val.toISOString().slice(0, 10);

    // Strings → escape quotes
    let str = String(val);
    if (str.includes('"')) str = str.replace(/"/g, '""');

    // Quote if contains comma or newline
    if (str.includes(',') || str.includes('\n')) return `"${str}"`;

    return str;
  }

  // Drop only the first column name
  const headers = (columnNames ?? data[0]).slice(1);

  // Build CSV lines
  const csvLines = [
    headers.map(formatCell).join(','),            
    ...data.map(row => row.map(formatCell).join(','))
  ];

  return csvLines.join('\n');
}

/**
 * Extract pixel IDs from data
 */
export function extractPixelIds(data, columnNames) {
  const pixelIdsIndex     = columnNames.indexOf('pixel_ids');
  const sensorNameIndex   = columnNames.indexOf('sensor_name');
  const campaignNameIndex = columnNames.indexOf('campaign_name');

  if (pixelIdsIndex === -1) return {};

  const grouped = {};

  data.forEach(row => {
    const pixelIdsArray  = row[pixelIdsIndex];
    const sensorName     = row[sensorNameIndex];
    const campaignName   = row[campaignNameIndex];

    if (!pixelIdsArray || !Array.isArray(pixelIdsArray)) return;

    const key = `${campaignName}|${sensorName}`;

    if (!grouped[key]) {
      grouped[key] = new Set();
    }

    pixelIdsArray.forEach(id => {
      grouped[key].add(typeof id === 'bigint' ? Number(id) : id);
    });
  });

  const result = {};
  for (const [key, ids] of Object.entries(grouped)) {
    result[key] = [...ids].sort((a, b) => a - b);
  }

  return result;
}