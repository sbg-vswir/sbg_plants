import React, { useState } from 'react';
import {
  Paper,
  Typography,
  Box,
  Stack,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Collapse,
} from '@mui/material';
import { TableChart as TableIcon, ExpandMore as ExpandMoreIcon, ExpandLess as ExpandLessIcon } from '@mui/icons-material';

function DataTable({ columns, data, summarizeValue, defaultCollapsed = false }) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <Paper elevation={2}>
      <Box sx={{ bgcolor: '#f5f5f5', p: 2, borderBottom: collapsed ? 'none' : '1px solid #ddd' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <TableIcon color="primary" />
          <Typography variant="h6">Data Table</Typography>
          {data.length > 0 && (
            <Chip label={`${data.length} rows`} size="small" color="primary" />
          )}
          <Box sx={{ flex: 1 }} />
          <IconButton size="small" onClick={() => setCollapsed(v => !v)}>
            {collapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
          </IconButton>
        </Stack>
      </Box>
      <Collapse in={!collapsed}>
        <TableContainer sx={{ maxHeight: 600 }}>
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                {columns.map(col => (
                  <TableCell key={col.key} sx={{ fontWeight: 'bold', bgcolor: '#fafafa' }}>
                    {col.label}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {data.map((row, idx) => (
                <TableRow key={idx} hover>
                  {columns.map(col => (
                    <TableCell key={col.key}>
                      {summarizeValue(row[col.key]) ?? '—'}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Collapse>
    </Paper>
  );
}

export default DataTable;
