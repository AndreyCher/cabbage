import { useEffect, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, FormControlLabel, LinearProgress, Stack, Switch, TextField, Typography } from '@mui/material'
import { controllerApi } from './controllerApi'

type Service = { id: string; name: string; enabled: boolean; used: number; limit: number; window: 'minute' | 'day' | string }
type Settings = { check_interval_seconds: number; unhealthy_retry_seconds: number; stale_after_seconds: number; timeout_seconds: number; retries: number; concurrency: number; failure_threshold: number; providers: string[]; services: Service[]; revision: number }

const windowLabel = (window: string) => window === 'minute' ? 'minute' : window === 'day' ? 'day' : window

export function ProxyCheckerSettings() {
  const [value, setValue] = useState<Settings | null>(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  useEffect(() => { controllerApi<Settings>('/settings/proxy-checker').then(setValue).catch((err) => setError(String(err))) }, [])
  if (!value) return error ? <Alert severity="error">{error}</Alert> : <Typography>Loading…</Typography>
  const number = (key: keyof Settings, label: string) => <TextField type="number" label={label} value={value[key]} onChange={(event) => setValue({ ...value, [key]: Number(event.target.value) })} />
  async function save() {
    if (!value) return
    try { const { revision: _, services: __, ...payload } = value; setValue(await controllerApi<Settings>('/settings/proxy-checker', { method: 'PUT', body: JSON.stringify(payload) })); setSaved(true); setError('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to save settings') }
  }
  return <Stack gap={2}>
    <Typography color="text.secondary">Database values override the autonomous proxy-checker config.json defaults. Changes are picked up without restart.</Typography>
    {error && <Alert severity="error">{error}</Alert>}{saved && <Alert severity="success">Settings saved.</Alert>}
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: 2 }}>{number('check_interval_seconds', 'Healthy check interval, sec')}{number('unhealthy_retry_seconds', 'Unhealthy retry interval, sec')}{number('stale_after_seconds', 'Result stale after, sec')}{number('timeout_seconds', 'Provider timeout, sec')}{number('retries', 'Retries')}{number('concurrency', 'Concurrent checks')}{number('failure_threshold', 'Failures before unhealthy')}</Box>
    <Box>
      <Typography variant="h6" mb={0.5}>Proxy location verification services</Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>Enable only the providers the checker may call. Usage is calculated from completed provider attempts in the current quota window.</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, minmax(0, 1fr))' }, gap: 2 }}>
        {value.services.map((service) => {
          const percentage = service.limit > 0 ? Math.min(100, service.used / service.limit * 100) : 0
          return <Card key={service.id} variant="outlined"><CardContent><Stack gap={1.5}>
            <FormControlLabel sx={{ m: 0, justifyContent: 'space-between' }} labelPlacement="start" label={<Box><Typography fontWeight={700}>{service.name}</Typography><Typography variant="caption" color="text.secondary">{service.id}</Typography></Box>} control={<Switch checked={value.providers.includes(service.id)} onChange={(event) => {
              const providers = event.target.checked ? [...value.providers, service.id] : value.providers.filter((provider) => provider !== service.id)
              setValue({ ...value, providers, services: value.services.map((item) => item.id === service.id ? { ...item, enabled: event.target.checked } : item) }); setSaved(false)
            }} />} />
            <LinearProgress variant="determinate" value={percentage} color={percentage >= 90 ? 'warning' : 'primary'} />
            <Typography variant="body2">{service.used.toLocaleString()} / {service.limit.toLocaleString()} per {windowLabel(service.window)}</Typography>
          </Stack></CardContent></Card>
        })}
      </Box>
    </Box>
    <Stack direction="row" justifyContent="space-between"><Typography variant="caption">Revision: {value.revision}</Typography><Button variant="contained" onClick={() => void save()}>Save proxy checker settings</Button></Stack>
  </Stack>
}
