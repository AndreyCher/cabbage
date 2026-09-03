import { useEffect, useState } from 'react'
import { Alert, Button, Stack, Typography } from '@mui/material'
import { controllerApi } from './controllerApi'
import { WorkerConfigEditor } from './WorkerConfigEditor'
import type { JsonObject } from './types'

type Defaults = { config: Record<string, unknown>; revision: number; updated_at: string }

export function DefaultIdentitySettings() {
  const [config, setConfig] = useState<JsonObject>({})
  const [revision, setRevision] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function load() {
    try {
      const result = await controllerApi<Defaults>('/settings/identity-defaults')
      setConfig(result.config); setRevision(result.revision); setError('')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to load defaults') }
  }
  useEffect(() => { void load() }, [])
  async function save() {
    try {
      const result = await controllerApi<Defaults>('/settings/identity-defaults', { method: 'PUT', body: JSON.stringify({ config }) })
      setRevision(result.revision); setMessage('Defaults saved. They will be used for newly created Identities.'); setError('')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save defaults') }
  }
  return <Stack gap={2}>
    <Typography variant="body2" color="text.secondary">Base configuration merged into every newly created Identity profile. Existing profiles are not changed.</Typography>
    {error && <Alert severity="error">{error}</Alert>}{message && <Alert severity="success">{message}</Alert>}
    <WorkerConfigEditor value={config} onChange={(next) => { setConfig(next); setMessage('') }} />
    <Stack direction="row" justifyContent="space-between" alignItems="center"><Typography variant="caption" color="text.secondary">Revision: {revision ?? '—'}</Typography><Button variant="contained" onClick={() => void save()}>Save defaults</Button></Stack>
  </Stack>
}
