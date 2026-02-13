import React from 'react';
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
  TableRow
} from '@mui/material';
import { TableChart as TableIcon } from '@mui/icons-material';

function DataTable({ columns, data, summarizeValue }) {
  return (
    <Paper elevation={2}>
      <Box sx={{ bgcolor: '#f5f5f5', p: 2, borderBottom: '1px solid #ddd' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <TableIcon color="primary" />
          <Typography variant="h6">Data Table</Typography>
          {data.length > 0 && (
            <Chip label={`${data.length} rows`} size="small" color="primary" />
          )}
        </Stack>
      </Box>
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
    </Paper>
  );
}

export default DataTable;