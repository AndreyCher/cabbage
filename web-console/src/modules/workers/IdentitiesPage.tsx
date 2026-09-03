import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions,
  DialogContent, DialogTitle, Stack, Table, TableBody, TableCell, TableHead,
  TableRow, Tab, Tabs, TextField, Typography,
} from '@mui/material'
import { AddRounded, DeleteForeverRounded, DeleteOutlineRounded, EditRounded, RefreshRounded } from '@mui/icons-material'
import { controllerApi } from './controllerApi'
import { ClientTablePagination, useClientPagination } from '../../components/ClientTablePagination'
import { WorkerConfigEditor } from './WorkerConfigEditor'
import { ProxySelect } from './ProxiesPage'
import type { Identity, JsonObject } from './types'

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
  const [config, setConfig] = useState<JsonObject>({})
  const [defaultProxyId, setDefaultProxyId] = useState<string | null>(null)
  const [tab, setTab] = useState('profile')
  const [runtimeProfile, setRuntimeProfile] = useState<JsonObject | null>(null)
  const [error, setError] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<Identity | null>(null)
  const [deleteAccountData, setDeleteAccountData] = useState(false)
  const pagination = useClientPagination(items, 'identities')

  const refresh = useCallback(async () => {
    try { setItems(await controllerApi<Identity[]>('/identities')); setError('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load Identities') }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  function edit(item: Identity) {
    setCreating(false); setSelected(item); setIdentity(item.identity)
    setConfig(item.config); setDefaultProxyId(item.default_proxy_config_id ?? null); setTab('profile'); setError('')
  }
  async function create() {
    setCreating(true); setSelected(null); setIdentity(''); setError('')
    try {
      const defaults = await controllerApi<{ config: Record<string, unknown> }>('/settings/identity-defaults')
      setConfig(defaults.config)
    } catch { setConfig(defaultConfig) }
    setDefaultProxyId(null); setTab('profile')
  }
  async function save() {
    try {
      if (creating) await controllerApi('/identities', { method: 'POST', body: JSON.stringify({ identity, config, default_proxy_config_id: defaultProxyId }) })
      else await controllerApi(`/identities/${encodeURIComponent(identity)}`, { method: 'PUT', body: JSON.stringify({ config, default_proxy_config_id: defaultProxyId }) })
      setSelected(null); setCreating(false); await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save Identity') }
  }
  const modalOpen = creating || selected !== null
  async function maintenance(action: 'reset' | 'update') {
    try { await controllerApi(`/identities/${encodeURIComponent(identity)}/${action}`, { method: 'POST' }); await refresh(); setError('') }
    catch (err) { setError(err instanceof Error ? err.message : `Unable to ${action} Identity`) }
  }
  async function inspectRuntime() {
    try { setRuntimeProfile(await controllerApi<JsonObject>(`/identities/${encodeURIComponent(identity)}/runtime-profile`)); setError('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load runtime profile') }
  }
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
      {pagination.pageItems.map((item) => <TableRow key={item.identity}><TableCell><Typography fontWeight={700}>{item.identity}</Typography></TableCell><TableCell><Chip size="small" label={item.in_use ? 'In use' : 'Available'} color={item.in_use ? 'warning' : 'success'} variant="outlined" /></TableCell><TableCell>{item.revision}</TableCell><TableCell>{new Date(item.updated_at).toLocaleString()}</TableCell><TableCell align="right"><Button startIcon={<EditRounded />} onClick={() => edit(item)}>Open</Button><Button color="error" disabled={item.in_use} startIcon={<DeleteOutlineRounded />} onClick={() => { setDeleteTarget(item); setDeleteAccountData(false); setError('') }}>Delete</Button></TableCell></TableRow>)}
      {!items.length && <TableRow><TableCell colSpan={5}><Typography color="text.secondary" textAlign="center" py={4}>No Identity profiles.</Typography></TableCell></TableRow>}
    </TableBody></Table></CardContent><ClientTablePagination count={items.length} {...pagination} /></Card>
    <Dialog open={modalOpen} onClose={() => { setSelected(null); setCreating(false) }} fullWidth maxWidth="md"><DialogTitle>{creating ? 'Create Identity' : `Edit ${identity}`}</DialogTitle><DialogContent><Stack gap={2} mt={1}>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="Identity name" value={identity} disabled={!creating} onChange={(event) => setIdentity(event.target.value)} required helperText="Letters, numbers, dots, underscores and hyphens." />
      <Tabs value={tab} onChange={(_, next) => setTab(next)} variant="scrollable" scrollButtons="auto"><Tab value="profile" label="Profile settings" /><Tab value="proxy" label="Proxy" />{!creating && <Tab value="maintenance" label="Maintenance" />}</Tabs>
      {tab === 'profile' && <WorkerConfigEditor value={config} onChange={setConfig} />}
      {tab === 'proxy' && <Stack gap={2}><Typography color="text.secondary">Used when a run does not select a proxy explicitly and its Scenario has no default proxy.</Typography><ProxySelect value={defaultProxyId} onChange={setDefaultProxyId} label="Identity default proxy" /></Stack>}
      {tab === 'maintenance' && <Stack gap={2}><Alert severity="info">Operations are queued safely when the Identity is active.</Alert><Stack direction={{ xs: 'column', sm: 'row' }} gap={1}><Button variant="outlined" onClick={() => void inspectRuntime()}>Inspect runtime profile</Button><Button variant="outlined" onClick={() => void maintenance('update')}>Update profile files</Button><Button color="warning" variant="outlined" onClick={() => void maintenance('reset')}>Reset profile files</Button></Stack></Stack>}
      {!creating && selected?.in_use && <Alert severity="warning">This Identity is active. Saved changes apply to the next run.</Alert>}
    </Stack></DialogContent><DialogActions><Button onClick={() => { setSelected(null); setCreating(false) }}>Cancel</Button><Button variant="contained" onClick={() => void save()} disabled={!identity.trim()}>Save</Button></DialogActions></Dialog>
    <Dialog open={Boolean(runtimeProfile)} onClose={() => setRuntimeProfile(null)} fullWidth maxWidth="md"><DialogTitle>Materialized runtime profile — {identity}</DialogTitle><DialogContent><Box component="pre" sx={{ overflow: 'auto', p: 2, bgcolor: 'action.hover', borderRadius: 1, fontSize: 12 }}>{JSON.stringify(runtimeProfile, null, 2)}</Box></DialogContent><DialogActions><Button onClick={() => setRuntimeProfile(null)}>Close</Button></DialogActions></Dialog>
    <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} maxWidth="sm" fullWidth><DialogTitle>Delete {deleteTarget?.identity}?</DialogTitle><DialogContent><Stack gap={2} mt={1}>
      {error && <Alert severity="error">{error}</Alert>}
      <Alert severity={deleteAccountData ? 'error' : 'warning'}>{deleteAccountData ? 'This permanently deletes the profile and persistent browser/account data. Run history and artifacts remain.' : 'This deletes only the PostgreSQL profile. Persistent browser/account data remains and can be reused by recreating the same Identity.'}</Alert>
      <Button color="error" variant={deleteAccountData ? 'contained' : 'outlined'} startIcon={<DeleteForeverRounded />} onClick={() => setDeleteAccountData((value) => !value)}>{deleteAccountData ? 'Account data will be deleted' : 'Also delete persistent account data'}</Button>
    </Stack></DialogContent><DialogActions><Button onClick={() => setDeleteTarget(null)}>Cancel</Button><Button color="error" variant="contained" onClick={() => void remove()}>{deleteAccountData ? 'Delete account permanently' : 'Delete profile'}</Button></DialogActions></Dialog>
  </>
}
