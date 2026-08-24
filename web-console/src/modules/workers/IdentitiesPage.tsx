import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions,
  DialogContent, DialogTitle, Stack, Table, TableBody, TableCell, TableHead,
  TableRow, TextField, Typography,
} from '@mui/material'
import { AddRounded, DeleteForeverRounded, DeleteOutlineRounded, EditRounded, RefreshRounded } from '@mui/icons-material'
import { controllerApi } from './controllerApi'

type Identity = {
  identity: string
  config: Record<string, unknown>
  revision: number
  created_at: string
  updated_at: string
  in_use: boolean
}

const defaultConfig = {
  fingerprint: {
    os: 'default', preset: 'default', screen: 'default', locale: 'default',
    window: 'default', device_pixel_ratio: 'default', hardware_concurrency: 'default',
    webgl: 'default', languages: 'default', timezone: 'default',
  },
}

export function IdentitiesPage() {
  const [items, setItems] = useState<Identity[]>([])
  const [selected, setSelected] = useState<Identity | null>(null)
  const [creating, setCreating] = useState(false)
  const [identity, setIdentity] = useState('')
  const [json, setJson] = useState('')
  const [error, setError] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<Identity | null>(null)
  const [deleteAccountData, setDeleteAccountData] = useState(false)

  const refresh = useCallback(async () => {
    try { setItems(await controllerApi<Identity[]>('/identities')); setError('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load Identities') }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  function edit(item: Identity) {
    setCreating(false); setSelected(item); setIdentity(item.identity)
    setJson(JSON.stringify(item.config, null, 2)); setError('')
  }
  async function create() {
    setCreating(true); setSelected(null); setIdentity(''); setError('')
    try {
      const defaults = await controllerApi<{ config: Record<string, unknown> }>('/settings/identity-defaults')
      setJson(JSON.stringify(defaults.config, null, 2))
    } catch { setJson(JSON.stringify(defaultConfig, null, 2)) }
  }
  async function save() {
    try {
      const config = JSON.parse(json) as Record<string, unknown>
      if (!config || Array.isArray(config) || typeof config !== 'object') throw new Error('Profile must be a JSON object')
      if (creating) await controllerApi('/identities', { method: 'POST', body: JSON.stringify({ identity, config }) })
      else await controllerApi(`/identities/${encodeURIComponent(identity)}`, { method: 'PUT', body: JSON.stringify({ config }) })
      setSelected(null); setCreating(false); await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save Identity') }
  }
  const modalOpen = creating || selected !== null
  async function remove() {
    if (!deleteTarget) return
    try {
      await controllerApi(`/identities/${encodeURIComponent(deleteTarget.identity)}?delete_account_data=${deleteAccountData}`, { method: 'DELETE' })
      setDeleteTarget(null); setDeleteAccountData(false); await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete Identity') }
  }

  return <>
    <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2} mb={3}>
      <Box><Typography variant="h4">Identities</Typography><Typography color="text.secondary" mt={.5}>Persistent browser profiles used by worker runs.</Typography></Box>
      <Stack direction="row" gap={1}><Button startIcon={<RefreshRounded />} onClick={() => void refresh()}>Refresh</Button><Button variant="contained" startIcon={<AddRounded />} onClick={create}>New Identity</Button></Stack>
    </Stack>
    {error && !modalOpen && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    <Card><CardContent sx={{ overflowX: 'auto' }}><Table><TableHead><TableRow><TableCell>Name</TableCell><TableCell>Status</TableCell><TableCell>Revision</TableCell><TableCell>Updated</TableCell><TableCell /></TableRow></TableHead><TableBody>
      {items.map((item) => <TableRow key={item.identity}><TableCell><Typography fontWeight={700}>{item.identity}</Typography></TableCell><TableCell><Chip size="small" label={item.in_use ? 'In use' : 'Available'} color={item.in_use ? 'warning' : 'success'} variant="outlined" /></TableCell><TableCell>{item.revision}</TableCell><TableCell>{new Date(item.updated_at).toLocaleString()}</TableCell><TableCell align="right"><Button startIcon={<EditRounded />} onClick={() => edit(item)}>Open</Button><Button color="error" disabled={item.in_use} startIcon={<DeleteOutlineRounded />} onClick={() => { setDeleteTarget(item); setDeleteAccountData(false); setError('') }}>Delete</Button></TableCell></TableRow>)}
      {!items.length && <TableRow><TableCell colSpan={5}><Typography color="text.secondary" textAlign="center" py={4}>No Identity profiles.</Typography></TableCell></TableRow>}
    </TableBody></Table></CardContent></Card>
    <Dialog open={modalOpen} onClose={() => { setSelected(null); setCreating(false) }} fullWidth maxWidth="md"><DialogTitle>{creating ? 'Create Identity' : `Edit ${identity}`}</DialogTitle><DialogContent><Stack gap={2} mt={1}>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="Identity name" value={identity} disabled={!creating} onChange={(event) => setIdentity(event.target.value)} required helperText="Letters, numbers, dots, underscores and hyphens." />
      <TextField label="Profile JSON" value={json} onChange={(event) => setJson(event.target.value)} multiline minRows={18} maxRows={30} InputProps={{ sx: { fontFamily: 'monospace', fontSize: 13 } }} />
      {!creating && selected?.in_use && <Alert severity="warning">This Identity is active. Saved changes apply to the next run.</Alert>}
    </Stack></DialogContent><DialogActions><Button onClick={() => { setSelected(null); setCreating(false) }}>Cancel</Button><Button variant="contained" onClick={() => void save()} disabled={!identity.trim() || !json.trim()}>Save</Button></DialogActions></Dialog>
    <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} maxWidth="sm" fullWidth><DialogTitle>Delete {deleteTarget?.identity}?</DialogTitle><DialogContent><Stack gap={2} mt={1}>
      {error && <Alert severity="error">{error}</Alert>}
      <Alert severity={deleteAccountData ? 'error' : 'warning'}>{deleteAccountData ? 'This permanently deletes the profile and persistent browser/account data. Run history and artifacts remain.' : 'This deletes only the PostgreSQL profile. Persistent browser/account data remains and can be reused by recreating the same Identity.'}</Alert>
      <Button color="error" variant={deleteAccountData ? 'contained' : 'outlined'} startIcon={<DeleteForeverRounded />} onClick={() => setDeleteAccountData((value) => !value)}>{deleteAccountData ? 'Account data will be deleted' : 'Also delete persistent account data'}</Button>
    </Stack></DialogContent><DialogActions><Button onClick={() => setDeleteTarget(null)}>Cancel</Button><Button color="error" variant="contained" onClick={() => void remove()}>{deleteAccountData ? 'Delete account permanently' : 'Delete profile'}</Button></DialogActions></Dialog>
  </>
}
