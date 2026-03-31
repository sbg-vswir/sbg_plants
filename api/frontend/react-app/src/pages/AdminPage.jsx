import React, { useState, useEffect } from 'react';
import {
  Container, Box, Typography, Button, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Paper, Chip, IconButton,
  Select, MenuItem, CircularProgress, Alert, TextField, FormGroup,
  FormControlLabel, Checkbox, Divider, Stack,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  GroupAdd as GroupAddIcon,
  PersonAdd as PersonAddIcon,
} from '@mui/icons-material';
import Navbar from '../components/Navbar';
import { useIsAdmin } from '../hooks/useIsAdmin';
import { adminApi } from '../utils/api';

const ALL_GROUPS = ['users', 'admins', 'superadmins'];

const PASSWORD_REQUIREMENTS = [
  'Minimum 8 characters',
  'At least one uppercase letter (A–Z)',
  'At least one lowercase letter (a–z)',
  'At least one number (0–9)',
  'At least one special character (e.g. !@#$%^&*)',
];

const EMPTY_FORM = { username: '', email: '', temporaryPassword: '', groups: ['users'] };

function AdminPage() {
  const { isAdmin, isSuperAdmin } = useIsAdmin();

  // User list state
  const [users, setUsers]     = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  // Group picker state
  const [groupPickerUser, setGroupPickerUser] = useState(null);
  const [selectedGroup, setSelectedGroup]     = useState('');

  // Create user form state
  const [showCreate, setShowCreate]   = useState(false);
  const [form, setForm]               = useState(EMPTY_FORM);
  const [formError, setFormError]     = useState('');
  const [creating, setCreating]       = useState(false);
  const [createSuccess, setCreateSuccess] = useState('');

  useEffect(() => { loadUsers(); }, []);

  async function loadUsers() {
    setLoading(true);
    setError('');
    try {
      setUsers(await adminApi.listUsers());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteUser(username) {
    if (!window.confirm(`Delete ${username}? This cannot be undone.`)) return;
    try {
      await adminApi.deleteUser(username);
      setUsers(u => u.filter(x => x.username !== username));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleAddToGroup(username, group) {
    try {
      await adminApi.addToGroup(username, group);
      setUsers(u => u.map(x =>
        x.username === username ? { ...x, groups: [...x.groups, group] } : x
      ));
      setGroupPickerUser(null);
      setSelectedGroup('');
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRemoveFromGroup(username, group) {
    try {
      await adminApi.removeFromGroup(username, group);
      setUsers(u => u.map(x =>
        x.username === username ? { ...x, groups: x.groups.filter(g => g !== group) } : x
      ));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCreateUser() {
    if (!form.username || !form.email || !form.temporaryPassword) {
      setFormError('All fields are required.');
      return;
    }
    setCreating(true);
    setFormError('');
    setCreateSuccess('');
    try {
      await adminApi.createUser(form);
      setCreateSuccess(`User "${form.username}" created successfully.`);
      setForm(EMPTY_FORM);
      loadUsers();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setCreating(false);
    }
  }

  function getAvailableGroupsForUser(user) {
    const notYetAssigned = ALL_GROUPS.filter(g => !user.groups.includes(g));
    return isSuperAdmin ? notYetAssigned : notYetAssigned.filter(g => g !== 'superadmins');
  }

  function canRemoveGroup(group) {
    return isSuperAdmin || group !== 'superadmins';
  }

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Navbar />
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <Stack direction={{ xs: 'column', lg: 'row' }} spacing={4} alignItems="flex-start">

          {/* ── User table ─────────────────────────────────────────────── */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
              <Typography variant="h5">User Management</Typography>
              {isAdmin && (
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<PersonAddIcon />}
                  onClick={() => { setShowCreate(s => !s); setFormError(''); setCreateSuccess(''); }}
                >
                  {showCreate ? 'Cancel' : 'Add User'}
                </Button>
              )}
            </Stack>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress />
              </Box>
            ) : (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: 'grey.50' }}>
                      <TableCell><strong>Username</strong></TableCell>
                      <TableCell><strong>Email</strong></TableCell>
                      <TableCell><strong>Status</strong></TableCell>
                      <TableCell><strong>Groups</strong></TableCell>
                      {isSuperAdmin && <TableCell align="right"><strong>Actions</strong></TableCell>}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {users.map(user => {
                      const availableGroups = getAvailableGroupsForUser(user);
                      return (
                        <TableRow key={user.username} hover>
                          <TableCell>{user.username}</TableCell>
                          <TableCell>{user.email}</TableCell>
                          <TableCell>
                            <Chip
                              label={user.status}
                              size="small"
                              color={
                                user.status === 'CONFIRMED' ? 'success' :
                                user.status === 'FORCE_CHANGE_PASSWORD' ? 'warning' : 'default'
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center' }}>
                              {user.groups.map(g => (
                                <Chip
                                  key={g}
                                  label={g}
                                  size="small"
                                  color="primary"
                                  variant="outlined"
                                  onDelete={canRemoveGroup(g) ? () => handleRemoveFromGroup(user.username, g) : undefined}
                                />
                              ))}
                              {availableGroups.length > 0 && (
                                groupPickerUser === user.username ? (
                                  <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                                    <Select
                                      size="small"
                                      value={selectedGroup}
                                      onChange={e => setSelectedGroup(e.target.value)}
                                      sx={{ fontSize: 12, height: 28 }}
                                    >
                                      {availableGroups.map(g => (
                                        <MenuItem key={g} value={g} sx={{ fontSize: 12 }}>{g}</MenuItem>
                                      ))}
                                    </Select>
                                    <Button
                                      size="small"
                                      variant="contained"
                                      sx={{ height: 28, fontSize: 11, minWidth: 'unset', px: 1.5 }}
                                      onClick={() => handleAddToGroup(user.username, selectedGroup)}
                                    >
                                      Add
                                    </Button>
                                    <IconButton size="small" onClick={() => { setGroupPickerUser(null); setSelectedGroup(''); }}>
                                      ✕
                                    </IconButton>
                                  </Box>
                                ) : (
                                  <Chip
                                    label="+ group"
                                    size="small"
                                    variant="outlined"
                                    icon={<GroupAddIcon />}
                                    onClick={() => { setGroupPickerUser(user.username); setSelectedGroup(availableGroups[0]); }}
                                    sx={{ cursor: 'pointer', borderStyle: 'dashed' }}
                                  />
                                )
                              )}
                            </Box>
                          </TableCell>
                          {isSuperAdmin && (
                            <TableCell align="right">
                              <IconButton size="small" color="error" onClick={() => handleDeleteUser(user.username)}>
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </TableCell>
                          )}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>

          {/* ── Create user panel ───────────────────────────────────────── */}
          {showCreate && isAdmin && (
            <Box
              component={Paper}
              variant="outlined"
              sx={{ p: 3, width: { xs: '100%', lg: 340 }, flexShrink: 0 }}
            >
              <Typography variant="h6" sx={{ mb: 2 }}>Create New User</Typography>

              {formError   && <Alert severity="error"   sx={{ mb: 2 }}>{formError}</Alert>}
              {createSuccess && <Alert severity="success" sx={{ mb: 2 }}>{createSuccess}</Alert>}

              <Stack spacing={2}>
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

                {/* Password requirements */}
                <Box sx={{ bgcolor: 'grey.50', border: '1px solid', borderColor: 'grey.200', borderRadius: 1, p: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5, fontWeight: 600 }}>
                    Password requirements
                  </Typography>
                  {PASSWORD_REQUIREMENTS.map(req => (
                    <Typography key={req} variant="caption" color="text.secondary" display="block">
                      · {req}
                    </Typography>
                  ))}
                </Box>

                <Divider />

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

                <Button
                  variant="contained"
                  onClick={handleCreateUser}
                  disabled={creating}
                  fullWidth
                >
                  {creating ? 'Creating...' : 'Create User'}
                </Button>
              </Stack>
            </Box>
          )}

        </Stack>
      </Container>
    </Box>
  );
}

export default AdminPage;
