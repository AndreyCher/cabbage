import { useEffect, useState } from 'react'
import { Alert, Button, Stack, Typography } from '@mui/material'
import { controllerApi } from './controllerApi'
import { WorkerConfigEditor } from './WorkerConfigEditor'
import type { JsonObject } from './types'

type Defaults = { config: JsonObject; revision: number; updated_at: string }

export function WorkerDefaultsSettings() {
  const [config, setConfig] = useState<JsonObject>({})
  const [revision, setRevision] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  async function load() {
    try { const result = await controllerApi<Defaults>('/settings/worker-defaults'); setConfig(result.config); setRevision(result.revision); setError('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load worker defaults') }
  }
  useEffect(() => { void load() }, [])
  async function save() {
    try { const result = await controllerApi<Defaults>('/settings/worker-defaults', { method: 'PUT', body: JSON.stringify({ config }) }); setRevision(result.revision); setMessage('Worker defaults saved. New runs will materialize them into the worker config directory.'); setError('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to save worker defaults') }
  }
  return <Stack gap={2}>
    <Typography variant="body2" color="text.secondary">Base worker configuration for every run. Run overrides and Identity settings are merged on top; the standalone worker remains compatible with files mounted directly into its config directory.</Typography>
    {error && <Alert severity="error">{error}</Alert>}{message && <Alert severity="success">{message}</Alert>}
    <WorkerConfigEditor value={config} onChange={(next) => { setConfig(next); setMessage('') }} />
    <Stack direction="row" justifyContent="space-between" alignItems="center"><Typography variant="caption" color="text.secondary">Revision: {revision ?? '—'}</Typography><Button variant="contained" onClick={() => void save()}>Save worker defaults</Button></Stack>
  </Stack>
}
