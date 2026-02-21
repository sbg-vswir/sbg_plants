// components/admin/CreateUserDialog.js
import React, { useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, TextField, FormGroup, FormControlLabel,
  Checkbox, Alert, Typography
} from '@mui/material';
import { adminApi } from '../utils/api';

const ALL_GROUPS = ['users', 'admins', 'superadmins'];

function CreateUserDialog({ open, onClose, onCreated }) {
  const [form, setForm] = useState({
    username: '',
    email: '',
    temporaryPassword: '',
    groups: ['users']
  });
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  function handleClose() {
    setForm({ username: '', email: '', temporaryPassword: '', groups: ['users'] });
    setError('');
    onClose();
  }

  async function handleSubmit() {
    if (!form.username || !form.email || !form.temporaryPassword) {
      setError('All fields are required.');
      return;
    }
    setCreating(true);
    setError('');
    try {
      await adminApi.createUser(form);
      handleClose();
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle>Create New User</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          label="Username"
          size="small"
          fullWidth
          value={form.username}
          onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
        />
        <TextField
          label="Email"
          type="email"
          size="small"
          fullWidth
          value={form.email}
          onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
        />
        <TextField
          label="Temporary Password"
          type="password"
          size="small"
          fullWidth
          value={form.temporaryPassword}
          onChange={e => setForm(f => ({ ...f, temporaryPassword: e.target.value }))}
        />
        <FormGroup>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>
            Groups
          </Typography>
          {ALL_GROUPS.map(g => (
            <FormControlLabel
              key={g}
              label={g}
              control={
                <Checkbox
                  size="small"
                  checked={form.groups.includes(g)}
                  onChange={e => setForm(f => ({
                    ...f,
                    groups: e.target.checked
                      ? [...f.groups, g]
                      : f.groups.filter(x => x !== g)
                  }))}
                />
              }
            />
          ))}
        </FormGroup>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={creating}>
          {creating ? 'Creating...' : 'Create User'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default CreateUserDialog;