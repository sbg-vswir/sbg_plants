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
  
  if (Array.isArray(v)) {
    if (v.length <= 2 * n) {
      return JSON.stringify(v, (key, value) =>
        typeof value === 'bigint' ? value.toString() : value
      );
    }
    return `[${v.slice(0, n).join(', ')}, ..., ${v.slice(-n).join(', ')}]`;
  }
  
  if (typeof v === 'object') {
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
    if (value) {
      if (key === 'plot_name') {
        filters[key] = value.split(',').map(p => p.trim());
      } else {
        filters[key] = value;
      }
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

/**
 * Convert data to CSV format
 */
export function convertToCSV(data) {
  if (!data.length) return '';
  
  const headers = Object.keys(data[0]);
  const rows = data.map(row => 
    headers.map(header => {
      const val = row[header];
      if (val === null || val === undefined) return '';
      if (typeof val === 'object') return JSON.stringify(val);
      return String(val).replace(/"/g, '""');
    }).map(v => `"${v}"`).join(',')
  );
  
  return [headers.join(','), ...rows].join('\n');
}

/**
 * Extract pixel IDs from data
 */
export function extractPixelIds(data, columnNames) {
  const pixelIds = new Set();
  const pixelIdsIndex = columnNames.indexOf('pixel_ids');
  
  if (pixelIdsIndex === -1) return [];
  
  data.forEach(row => {
    const pixelIdsArray = row[pixelIdsIndex];
    if (pixelIdsArray && Array.isArray(pixelIdsArray)) {
      pixelIdsArray.forEach(id => {
        // Convert BigInt to Number
        const numericId = typeof id === 'bigint' ? Number(id) : id;
        pixelIds.add(numericId);
      });
    }
  });
  
  return [...pixelIds].sort((a, b) => a - b);
}