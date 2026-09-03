import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent,
  DialogTitle, FormControl, FormControlLabel, InputLabel, MenuItem, Select, Stack,
  Switch, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material'
import { AddRounded, DeleteOutlineRounded, EditRounded, RefreshRounded } from '@mui/icons-material'
import { controllerApi } from './controllerApi'
import type { ProxyConfig } from './types'

type Form = {
  name: string; scheme: 'http' | 'https'; host: string; port: number; username: string;
  password: string; bypass: string; verify_ssl: boolean; geo_enabled: boolean;
  geo_validate: boolean; geo_fail: boolean; enabled: boolean
}

const emptyForm: Form = { name: '', scheme: 'http', host: '', port: 8080, username: '', password: '', bypass: '', verify_ssl: true, geo_enabled: true, geo_validate: true, geo_fail: false, enabled: true }

export function ProxySelect({ value, onChange, label = 'Default proxy', allowNone = true }: { value?: string | null; onChange: (value: string | null) => void; label?: string; allowNone?: boolean }) {
  const [items, setItems] = useState<ProxyConfig[]>([])
  const [error, setError] = useState('')
  useEffect(() => { controllerApi<ProxyConfig[]>('/proxies').then(setItems).catch((err) => setError(err instanceof Error ? err.message : 'Unable to load proxies')) }, [])
  return <Stack gap={1}><FormControl size="small" fullWidth error={Boolean(error)}><InputLabel>{label}</InputLabel><Select label={label} value={value ?? ''} onChange={(event) => onChange(event.target.value ? String(event.target.value) : null)}>{allowNone && <MenuItem value="">No proxy</MenuItem>}{items.map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · {item.scheme}://{item.host}:{item.port}</MenuItem>)}</Select></FormControl>{error && <Typography variant="caption" color="error">{error}</Typography>}</Stack>
}

export function ProxiesPage() {
  const [items, setItems] = useState<ProxyConfig[]>([])
  const [selected, setSelected] = useState<ProxyConfig | null>(null)
  const [form, setForm] = useState<Form>(emptyForm)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => { try { setItems(await controllerApi<ProxyConfig[]>('/proxies')); setError('') } catch (err) { setError(err instanceof Error ? err.message : 'Unable to load proxies') } }, [])
  useEffect(() => { void refresh() }, [refresh])
  function create() { setSelected(null); setForm(emptyForm); setOpen(true); setError('') }
  function edit(item: ProxyConfig) {
    setSelected(item); setForm({ name: item.name, scheme: item.scheme, host: item.host, port: item.port, username: item.username ?? '', password: '', bypass: item.bypass ?? '', verify_ssl: item.verify_ssl, geo_enabled: item.geoip.enabled, geo_validate: item.geoip.validate_identity, geo_fail: item.geoip.fail_on_mismatch, enabled: item.enabled }); setOpen(true); setError('')
  }
  async function save() {
    const payload = { name: form.name, scheme: form.scheme, host: form.host, port: form.port, username: form.username || null, ...(form.password ? { password: form.password } : {}), bypass: form.bypass || null, verify_ssl: form.verify_ssl, ...(selected ? { enabled: form.enabled } : {}), geoip: { enabled: form.geo_enabled, validate_identity: form.geo_validate, fail_on_mismatch: form.geo_fail } }
    try { await controllerApi(selected ? `/proxies/${selected.id}` : '/proxies', { method: selected ? 'PUT' : 'POST', body: JSON.stringify(payload) }); setOpen(false); await refresh() } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save proxy') }
  }
  async function remove(item: ProxyConfig) { if (!window.confirm(`Disable proxy ${item.name}? Existing run history will be preserved.`)) return; try { await controllerApi(`/proxies/${item.id}`, { method: 'DELETE' }); await refresh() } catch (err) { setError(err instanceof Error ? err.message : 'Unable to disable proxy') } }

  return <>
    <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2} mb={3}><Box><Typography variant="h4">Proxies</Typography><Typography color="text.secondary" mt={.5}>Reusable network identities for Identities, Scenarios and individual runs.</Typography></Box><Stack direction="row" gap={1}><Button startIcon={<RefreshRounded />} onClick={() => void refresh()}>Refresh</Button><Button variant="contained" startIcon={<AddRounded />} onClick={create}>New proxy</Button></Stack></Stack>
    {error && !open && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    <Card><CardContent sx={{ overflowX: 'auto' }}><Table sx={{ minWidth: 850 }}><TableHead><TableRow><TableCell>Name</TableCell><TableCell>Endpoint</TableCell><TableCell>Authentication</TableCell><TableCell>GEO policy</TableCell><TableCell>TLS</TableCell><TableCell>Status</TableCell><TableCell /></TableRow></TableHead><TableBody>{items.map((item) => <TableRow key={item.id}><TableCell><Typography fontWeight={700}>{item.name}</Typography></TableCell><TableCell>{item.scheme}://{item.host}:{item.port}</TableCell><TableCell>{item.username || item.has_password ? item.username || 'Password only' : 'None'}</TableCell><TableCell>{item.geoip.enabled ? item.geoip.fail_on_mismatch ? 'Strict match' : item.geoip.validate_identity ? 'Validate / warn' : 'Lookup only' : 'Disabled'}</TableCell><TableCell>{item.verify_ssl ? 'Verify' : 'Skip verification'}</TableCell><TableCell><Chip size="small" label={item.enabled ? 'Enabled' : 'Disabled'} color={item.enabled ? 'success' : 'default'} variant="outlined" /></TableCell><TableCell align="right"><Button startIcon={<EditRounded />} onClick={() => edit(item)}>Edit</Button><Button color="error" startIcon={<DeleteOutlineRounded />} onClick={() => void remove(item)}>Disable</Button></TableCell></TableRow>)}{!items.length && <TableRow><TableCell colSpan={7}><Typography textAlign="center" color="text.secondary" py={4}>No active proxy configurations.</Typography></TableCell></TableRow>}</TableBody></Table></CardContent></Card>
    <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="md"><DialogTitle>{selected ? `Edit ${selected.name}` : 'Create proxy'}</DialogTitle><DialogContent><Stack gap={2} mt={1}>{error && <Alert severity="error">{error}</Alert>}<Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}><TextField label="Name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /><FormControl><InputLabel>Scheme</InputLabel><Select label="Scheme" value={form.scheme} onChange={(event) => setForm({ ...form, scheme: event.target.value as 'http' | 'https' })}><MenuItem value="http">HTTP</MenuItem><MenuItem value="https">HTTPS</MenuItem></Select></FormControl><TextField label="Host" value={form.host} onChange={(event) => setForm({ ...form, host: event.target.value })} required /><TextField label="Port" type="number" value={form.port} onChange={(event) => setForm({ ...form, port: Number(event.target.value) })} required /><TextField label="Username" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /><TextField label={selected?.has_password ? 'New password (leave blank to keep)' : 'Password'} type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></Box><TextField label="Bypass hosts" value={form.bypass} onChange={(event) => setForm({ ...form, bypass: event.target.value })} helperText="Comma-separated hosts that should bypass this proxy." /><Stack direction={{ xs: 'column', sm: 'row' }} flexWrap="wrap" gap={1}><FormControlLabel control={<Switch checked={form.verify_ssl} onChange={(event) => setForm({ ...form, verify_ssl: event.target.checked })} />} label="Verify TLS" /><FormControlLabel control={<Switch checked={form.geo_enabled} onChange={(event) => setForm({ ...form, geo_enabled: event.target.checked })} />} label="GEO lookup" /><FormControlLabel control={<Switch checked={form.geo_validate} onChange={(event) => setForm({ ...form, geo_validate: event.target.checked })} />} label="Validate Identity GEO" /><FormControlLabel control={<Switch checked={form.geo_fail} onChange={(event) => setForm({ ...form, geo_fail: event.target.checked })} />} label="Fail on mismatch" /></Stack></Stack></DialogContent><DialogActions><Button onClick={() => setOpen(false)}>Cancel</Button><Button variant="contained" disabled={!form.name.trim() || !form.host.trim() || form.port < 1 || form.port > 65535} onClick={() => void save()}>Save proxy</Button></DialogActions></Dialog>
  </>
}
