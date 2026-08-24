import { useEffect, useState } from 'react'
import { Alert, Button, Stack, TextField, Typography } from '@mui/material'
import { controllerApi } from './controllerApi'

type Defaults = { config: Record<string, unknown>; revision: number; updated_at: string }

export function DefaultIdentitySettings() {
  const [json, setJson] = useState('')
  const [revision, setRevision] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function load() {
    try {
      const result = await controllerApi<Defaults>('/settings/identity-defaults')
      setJson(JSON.stringify(result.config, null, 2)); setRevision(result.revision); setError('')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to load defaults') }
  }
  useEffect(() => { void load() }, [])
  async function save() {
    try {
      const config = JSON.parse(json) as Record<string, unknown>
      if (!config || Array.isArray(config) || typeof config !== 'object') throw new Error('Defaults must be a JSON object')
      const result = await controllerApi<Defaults>('/settings/identity-defaults', { method: 'PUT', body: JSON.stringify({ config }) })
      setRevision(result.revision); setMessage('Defaults saved. They will be used for newly created Identities.'); setError('')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save defaults') }
  }
  return <Stack gap={2}>
    <Typography variant="body2" color="text.secondary">Base configuration merged into every newly created Identity profile. Existing profiles are not changed.</Typography>
    {error && <Alert severity="error">{error}</Alert>}{message && <Alert severity="success">{message}</Alert>}
    <TextField value={json} onChange={(event) => { setJson(event.target.value); setMessage('') }} multiline minRows={14} maxRows={28} InputProps={{ sx: { fontFamily: 'monospace', fontSize: 13 } }} />
    <Stack direction="row" justifyContent="space-between" alignItems="center"><Typography variant="caption" color="text.secondary">Revision: {revision ?? '—'}</Typography><Button variant="contained" onClick={() => void save()}>Save defaults</Button></Stack>
  </Stack>
}
