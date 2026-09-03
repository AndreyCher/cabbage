import { useEffect, useState } from 'react'
import {
  Alert, Box, FormControl, FormControlLabel, InputLabel, MenuItem, Select,
  Stack, Switch, Tab, Tabs, TextField, Typography,
} from '@mui/material'
import type { JsonObject } from './types'

type Props = {
  value: JsonObject
  onChange: (value: JsonObject) => void
  compact?: boolean
}

function nested(source: JsonObject, group: string): JsonObject {
  const value = source[group]
  return value && typeof value === 'object' && !Array.isArray(value) ? value as JsonObject : {}
}

function setGroup(source: JsonObject, group: string, key: string, value: unknown): JsonObject {
  return { ...source, [group]: { ...nested(source, group), [key]: value } }
}

function BoolField({ label, value, onChange }: { label: string; value: boolean; onChange: (value: boolean) => void }) {
  return <FormControlLabel control={<Switch checked={value} onChange={(event) => onChange(event.target.checked)} />} label={label} />
}

function NumberField({ label, value, onChange, min, max, step }: { label: string; value: number; onChange: (value: number) => void; min?: number; max?: number; step?: number }) {
  return <TextField size="small" type="number" label={label} value={value} onChange={(event) => onChange(Number(event.target.value))} inputProps={{ min, max, step }} />
}

function JsonValueField({ label, value, onChange, helperText }: { label: string; value: unknown; onChange: (value: unknown) => void; helperText?: string }) {
  const [draft, setDraft] = useState(() => JSON.stringify(value ?? 'default', null, 2))
  const [error, setError] = useState('')
  return <TextField size="small" label={label} value={draft} helperText={error || helperText} error={Boolean(error)} multiline minRows={2}
    onChange={(event) => setDraft(event.target.value)}
    onBlur={() => { try { onChange(JSON.parse(draft)); setError('') } catch { setError('Invalid JSON value') } }}
    InputProps={{ sx: { fontFamily: 'monospace', fontSize: 12 } }} />
}

export function WorkerConfigEditor({ value, onChange, compact = false }: Props) {
  const [tab, setTab] = useState('browser')
  const browser = nested(value, 'browser')
  const recording = nested(value, 'recording')
  const fingerprint = nested(value, 'fingerprint')
  const fpDiagnostics = nested(value, 'fingerprint_diagnostics')
  const vmDiagnostics = nested(value, 'vm_diagnostics')
  const debug = nested(value, 'debug')
  const identityPolicy = nested(value, 'identity_policy')
  const plugins = nested(value, 'plugins')
  const [advancedDraft, setAdvancedDraft] = useState(() => JSON.stringify(value, null, 2))
  const [advancedError, setAdvancedError] = useState('')
  useEffect(() => setAdvancedDraft(JSON.stringify(value, null, 2)), [value])

  const group = (name: string, key: string, next: unknown) => onChange(setGroup(value, name, key, next))
  const grid = { display: 'grid', gridTemplateColumns: { xs: '1fr', sm: compact ? '1fr' : 'repeat(2, minmax(0, 1fr))' }, gap: 2 }

  return <Box>
    <Tabs value={tab} onChange={(_, next) => setTab(next)} variant="scrollable" scrollButtons="auto" sx={{ mb: 2 }}>
      <Tab value="browser" label="Browser" /><Tab value="profile" label="Fingerprint" /><Tab value="recording" label="Recording" />
      <Tab value="diagnostics" label="Diagnostics" /><Tab value="plugins" label="Plugins" /><Tab value="advanced" label="Advanced JSON" />
    </Tabs>
    {tab === 'browser' && <Stack gap={2}>
      <Box sx={grid}>
        <FormControl size="small"><InputLabel>Browser mode</InputLabel><Select label="Browser mode" value={String(browser.mode ?? 'virtual')} onChange={(event) => group('browser', 'mode', event.target.value)}><MenuItem value="virtual">Virtual</MenuItem><MenuItem value="headless">Headless</MenuItem><MenuItem value="debug">Debug</MenuItem></Select></FormControl>
        <TextField size="small" label="Browser version" value={String(browser.version ?? '152.0.4-beta.28')} onChange={(event) => group('browser', 'version', event.target.value)} />
        <NumberField label="Humanize" value={Number(browser.humanize ?? 1.8)} min={0} step={0.1} onChange={(next) => group('browser', 'humanize', next)} />
        <NumberField label="Startup attempts" value={Number(browser.startup_attempts ?? 3)} min={1} max={20} onChange={(next) => group('browser', 'startup_attempts', next)} />
        <NumberField label="Retry delay (seconds)" value={Number(browser.startup_retry_delay_sec ?? 1)} min={0} step={0.1} onChange={(next) => group('browser', 'startup_retry_delay_sec', next)} />
      </Box>
      <BoolField label="Enable browser cache" value={Boolean(browser.enable_cache ?? true)} onChange={(next) => group('browser', 'enable_cache', next)} />
      <Typography variant="subtitle2">Debug display</Typography>
      <JsonValueField label="browser.debug_display" value={browser.debug_display ?? { size: 'identity', fallback: { width: 1920, height: 1080 }, depth: 24, window: 'maximized', position: { x: 0, y: 0 }, novnc_scaling: 'local' }} onChange={(next) => group('browser', 'debug_display', next)} helperText="Identity/custom size, desktop geometry, window placement and noVNC scaling." />
      <BoolField label="Allow proxy changes for an existing Identity" value={Boolean(identityPolicy.allow_proxy_change ?? false)} onChange={(next) => group('identity_policy', 'allow_proxy_change', next)} />
      <BoolField label="Keep debug browser alive after automation" value={Boolean(debug.keep_alive ?? false)} onChange={(next) => group('debug', 'keep_alive', next)} />
      <TextField size="small" label="Debug message" value={String(debug.message ?? '')} onChange={(event) => group('debug', 'message', event.target.value)} />
    </Stack>}
    {tab === 'profile' && <Box sx={grid}>{['os', 'preset', 'screen', 'locale', 'languages', 'timezone', 'window', 'device_pixel_ratio', 'hardware_concurrency', 'webgl'].map((key) => <JsonValueField key={key} label={key.replaceAll('_', ' ')} value={fingerprint[key] ?? 'default'} onChange={(next) => group('fingerprint', key, next)} />)}</Box>}
    {tab === 'recording' && <Stack gap={2}>
      <BoolField label="Record video" value={Boolean(recording.video ?? true)} onChange={(next) => group('recording', 'video', next)} />
      <Box sx={grid}>
        <FormControl size="small"><InputLabel>Normal backend</InputLabel><Select label="Normal backend" value={String(recording.backend ?? 'x11')} onChange={(event) => group('recording', 'backend', event.target.value)}><MenuItem value="x11">X11 / FFmpeg</MenuItem><MenuItem value="playwright">Playwright</MenuItem></Select></FormControl>
        <FormControl size="small"><InputLabel>Debug backend</InputLabel><Select label="Debug backend" value={String(recording.debug_backend ?? 'x11')} onChange={(event) => group('recording', 'debug_backend', event.target.value)}><MenuItem value="x11">X11 / FFmpeg</MenuItem><MenuItem value="playwright">Playwright</MenuItem></Select></FormControl>
        <JsonValueField label="Video size" value={recording.video_size ?? 'default'} onChange={(next) => group('recording', 'video_size', next)} />
        <NumberField label="FPS" value={Number(recording.debug_fps ?? 15)} min={1} max={120} onChange={(next) => group('recording', 'debug_fps', next)} />
      </Box>
      <BoolField label="Show cursor marker" value={Boolean(recording.show_cursor ?? false)} onChange={(next) => group('recording', 'show_cursor', next)} />
    </Stack>}
    {tab === 'diagnostics' && <Stack gap={3}>
      <Box><Typography variant="subtitle2" mb={1}>Fingerprint diagnostics</Typography><Stack direction={{ xs: 'column', sm: 'row' }} flexWrap="wrap" gap={1}><BoolField label="Enabled" value={Boolean(fpDiagnostics.enabled ?? true)} onChange={(next) => group('fingerprint_diagnostics', 'enabled', next)} /><BoolField label="Save snapshot" value={Boolean(fpDiagnostics.save_snapshot ?? true)} onChange={(next) => group('fingerprint_diagnostics', 'save_snapshot', next)} /><BoolField label="Compare baseline" value={Boolean(fpDiagnostics.compare_with_baseline ?? true)} onChange={(next) => group('fingerprint_diagnostics', 'compare_with_baseline', next)} /><BoolField label="Update baseline" value={Boolean(fpDiagnostics.update_baseline ?? false)} onChange={(next) => group('fingerprint_diagnostics', 'update_baseline', next)} /><BoolField label="Fail on change" value={Boolean(fpDiagnostics.fail_on_change ?? false)} onChange={(next) => group('fingerprint_diagnostics', 'fail_on_change', next)} /></Stack></Box>
      <Box><Typography variant="subtitle2" mb={1}>VM diagnostics</Typography><Stack direction={{ xs: 'column', sm: 'row' }} flexWrap="wrap" gap={1}><BoolField label="Enabled" value={Boolean(vmDiagnostics.enabled ?? false)} onChange={(next) => group('vm_diagnostics', 'enabled', next)} /><BoolField label="Save snapshot" value={Boolean(vmDiagnostics.save_snapshot ?? true)} onChange={(next) => group('vm_diagnostics', 'save_snapshot', next)} /><BoolField label="Compare baseline" value={Boolean(vmDiagnostics.compare_with_baseline ?? true)} onChange={(next) => group('vm_diagnostics', 'compare_with_baseline', next)} /><BoolField label="Update baseline" value={Boolean(vmDiagnostics.update_baseline ?? false)} onChange={(next) => group('vm_diagnostics', 'update_baseline', next)} /><BoolField label="Keep history" value={Boolean(vmDiagnostics.keep_history ?? true)} onChange={(next) => group('vm_diagnostics', 'keep_history', next)} /></Stack><TextField size="small" sx={{ mt: 1 }} label="VM label" value={String(vmDiagnostics.label ?? 'unknown')} onChange={(event) => group('vm_diagnostics', 'label', event.target.value)} /></Box>
    </Stack>}
    {tab === 'plugins' && <Stack gap={2}><BoolField label="Enable plugin framework" value={Boolean(plugins.enabled ?? true)} onChange={(next) => group('plugins', 'enabled', next)} /><JsonValueField label="Plugin adapters and configuration" value={plugins.items ?? {}} onChange={(next) => group('plugins', 'items', next)} helperText="Adapter paths are advanced settings; plugin-specific config remains structured JSON." /></Stack>}
    {tab === 'advanced' && <Stack gap={1}>
      <Alert severity="info">Complete validated domain configuration. Infrastructure fields such as image, mounts, network and API bind are not accepted.</Alert>
      <TextField value={advancedDraft} multiline minRows={18} maxRows={32} error={Boolean(advancedError)} helperText={advancedError || 'Changes are applied when the field loses focus.'} onChange={(event) => setAdvancedDraft(event.target.value)} onBlur={() => { try { const parsed = JSON.parse(advancedDraft); if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error(); onChange(parsed); setAdvancedError('') } catch { setAdvancedError('Configuration must be a JSON object') } }} InputProps={{ sx: { fontFamily: 'monospace', fontSize: 12 } }} />
    </Stack>}
  </Box>
}
