// components/admin/AdminDialog.js
import React, { useState, useEffect } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Paper, Chip, Box, IconButton,
  Select, MenuItem, CircularProgress, Alert
} from '@mui/material';
import {
  Delete as DeleteIcon,
  GroupAdd as GroupAddIcon,
  PersonAdd as PersonAddIcon,
} from '@mui/icons-material';
import { useIsAdmin } from '../hooks/useIsAdmin';
import { adminApi } from '../utils/api';
import CreateUserDialog from './CreateUserDialog';

const ALL_GROUPS = ['users', 'admins', 'superadmins'];

function AdminDialog({ open, onClose }) {
  const { isAdmin, isSuperAdmin, groups: currentUserGroups } = useIsAdmin();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [groupPickerUser, setGroupPickerUser] = useState(null);
  const [selectedGroup, setSelectedGroup] = useState('');

  useEffect(() => {
    if (open) loadUsers();
  }, [open]);

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

  // Admins cannot add superadmins group unless they are a superadmin themselves
  function getAvailableGroupsForUser(user) {
    const notYetAssigned = ALL_GROUPS.filter(g => !user.groups.includes(g));
    if (isSuperAdmin) return notYetAssigned;
    // regular admins cannot assign superadmins group
    return notYetAssigned.filter(g => g !== 'superadmins');
  }

  // Admins cannot remove superadmins group from someone unless they are a superadmin
  function canRemoveGroup(group) {
    if (isSuperAdmin) return true;
    return group !== 'superadmins';
  }

  function openGroupPicker(username, availableGroups) {
    setGroupPickerUser(username);
    setSelectedGroup(availableGroups[0]);
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          User Management
          {isAdmin && (
            <Button
              variant="contained"
              size="small"
              startIcon={<PersonAddIcon />}
              onClick={() => setCreateOpen(true)}
            >
              Add User
            </Button>
          )}
        </DialogTitle>

        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
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
                                  onClick={() => openGroupPicker(user.username, availableGroups)}
                                  sx={{ cursor: 'pointer', borderStyle: 'dashed' }}
                                />
                              )
                            )}
                          </Box>
                        </TableCell>
                        {isSuperAdmin && (
                          <TableCell align="right">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleDeleteUser(user.username)}
                            >
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
        </DialogContent>

        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>

      <CreateUserDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => { setCreateOpen(false); loadUsers(); }}
      />
    </>
  );
}

export default AdminDialog;