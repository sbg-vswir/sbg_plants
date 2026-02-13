/**
 * Parquet parsing utilities using hyparquet
 */

import { parquetRead } from 'hyparquet';

export async function parseParquetData(arrayBuffer, columnNames) {
  try {
    // console.log('Parsing Parquet, buffer size:', arrayBuffer.byteLength);
    
    const rows = [];
    
    await parquetRead({
      file: arrayBuffer,
      onComplete: (data) => {
        data.forEach(row => rows.push(row));
      }
    });
    
    // console.log('Parquet parsed successfully. Rows:', rows.length);
    const geomIndex = columnNames ? columnNames.indexOf('geom') : -1;
    let geojson = null;
    const hasGeometry = rows.length > 0 && geomIndex > -1 && rows[0][geomIndex] !== undefined && rows[0][geomIndex] !== null;

    // // Process geometry
    // let geojson = null;
    // console.log(rows.length > 0 && rows[0].geom !== undefined && rows[0].geom !== null)
    // const hasGeometry = rows.length > 0 && rows[0].geom !== undefined && rows[0].geom !== null;
    // console.log(hasGeometry);
    if (hasGeometry) {
      geojson = createGeoJSON(rows, columnNames, geomIndex);
    }
    // console.log(geojson);
    return { data: rows, geojson: geojson, schema: null };
    
  } catch (error) {
    console.error('Error parsing Parquet:', error);
    throw new Error(`Failed to parse Parquet data: ${error.message}`);
  }
}

function createGeoJSON(rows, columnNames, geomIndex) {
  const features = rows
    .filter(row => row[geomIndex] !== null && row[geomIndex] !== undefined)
    .map(row => {
      let geometry;
      
      if (typeof row[geomIndex] === 'string') {
        geometry = parseWKT(row[geomIndex]);
      } else if (typeof row[geomIndex] === 'object' && row[geomIndex].type) {
        geometry = row[geomIndex];
      }
      
      if (!geometry) return null;
      
      return {
        type: 'Feature',
        geometry: geometry,
        properties: {}
      };
    })
    .filter(feature => feature !== null);
  
  return {
    type: 'FeatureCollection',
    features: features
  };
}

function parseWKT(wkt) {
  if (!wkt || typeof wkt !== 'string') return null;
  
  const pointMatch = wkt.match(/POINT\s*\(\s*([0-9.-]+)\s+([0-9.-]+)\s*\)/i);
  if (pointMatch) {
    return {
      type: 'Point',
      coordinates: [parseFloat(pointMatch[1]), parseFloat(pointMatch[2])]
    };
  }
  
  const polygonMatch = wkt.match(/POLYGON\s*\(\(([^)]+)\)\)/i);
  if (polygonMatch) {
    const coords = polygonMatch[1]
      .split(',')
      .map(pair => {
        const [x, y] = pair.trim().split(/\s+/);
        return [parseFloat(x), parseFloat(y)];
      });
    return {
      type: 'Polygon',
      coordinates: [coords]
    };
  }
  
  return null;
}

function summarizeValue(v, n = 2) {
  if (v === null || v === undefined) return v;
  
  if (Array.isArray(v)) {
    if (v.length <= 2 * n) return JSON.stringify(v);
    return `[${v.slice(0, n).join(', ')}, ..., ${v.slice(-n).join(', ')}]`;
  }
  
  if (typeof v === 'object') return JSON.stringify(v);
  
  return v;
}