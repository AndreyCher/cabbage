import { useEffect, useState } from 'react'
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material'
import { controllerApi } from './controllerApi'

type Settings = { check_interval_seconds: number; unhealthy_retry_seconds: number; stale_after_seconds: number; timeout_seconds: number; retries: number; concurrency: number; failure_threshold: number; providers: string[]; revision: number }

export function ProxyCheckerSettings() {
  const [value, setValue] = useState<Settings | null>(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  useEffect(() => { controllerApi<Settings>('/settings/proxy-checker').then(setValue).catch((err) => setError(String(err))) }, [])
  if (!value) return error ? <Alert severity="error">{error}</Alert> : <Typography>Loading…</Typography>
  const number = (key: keyof Settings, label: string) => <TextField type="number" label={label} value={value[key]} onChange={(event) => setValue({ ...value, [key]: Number(event.target.value) })} />
  async function save() {
    if (!value) return
    try { const { revision: _, ...payload } = value; setValue(await controllerApi<Settings>('/settings/proxy-checker', { method: 'PUT', body: JSON.stringify(payload) })); setSaved(true); setError('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to save settings') }
  }
  return <Stack gap={2}>
    <Typography color="text.secondary">Database values override the autonomous proxy-checker config.json defaults. Changes are picked up without restart.</Typography>
    {error && <Alert severity="error">{error}</Alert>}{saved && <Alert severity="success">Settings saved.</Alert>}
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: 2 }}>{number('check_interval_seconds', 'Healthy check interval, sec')}{number('unhealthy_retry_seconds', 'Unhealthy retry interval, sec')}{number('stale_after_seconds', 'Result stale after, sec')}{number('timeout_seconds', 'Provider timeout, sec')}{number('retries', 'Retries')}{number('concurrency', 'Concurrent checks')}{number('failure_threshold', 'Failures before unhealthy')}</Box>
    <TextField label="Provider order" value={value.providers.join(', ')} onChange={(event) => setValue({ ...value, providers: event.target.value.split(',').map((item) => item.trim()).filter(Boolean) })} helperText="Built-ins: ipwhois, freeipapi, ipapi_co. Paid adapters can be added in proxy-checker/config.json." />
    <Stack direction="row" justifyContent="space-between"><Typography variant="caption">Revision: {value.revision}</Typography><Button variant="contained" onClick={() => void save()}>Save proxy checker settings</Button></Stack>
  </Stack>
}
