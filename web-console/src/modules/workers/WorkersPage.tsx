import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, FormControlLabel, InputLabel,
  IconButton, MenuItem, Select, Stack, Switch, Table, TableBody, TableCell, TableHead,
  TableRow, TableSortLabel, TextField, Tooltip, Typography,
} from '@mui/material'
import { AddRounded, BugReportRounded, DescriptionRounded, LiveTvRounded, PlayCircleRounded, RefreshRounded, StopRounded } from '@mui/icons-material'
import { ClientTablePagination, useClientPagination } from '../../components/ClientTablePagination'

const apiRoot = '/api/controller/api/v1'
type Run = { id: string; identity: string; scenario_name: string; scenario_version: number; status: string; priority: number; current_stage?: string; created_at: string; debug: boolean; live_stream_available: boolean; recorded_video_available: boolean }
type RunMedia = { live: boolean; videos: Array<{ name: string; size: number }> }
type MediaDialog = { run: Run; ticket: string; live: boolean; videos: Array<{ name: string; size: number }> }
type Scenario = { id: string; name: string; version: number }
type Proxy = { id: string; name: string }
type Identity = { identity: string; in_use: boolean }
type SortColumn = 'identity' | 'scenario' | 'stage' | 'priority' | 'created' | 'status'
type SortDirection = 'asc' | 'desc'

const createdTimeFormatter = new Intl.DateTimeFormat(undefined, {
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short',
})

function token() { return localStorage.getItem('controller.api.token') ?? '' }
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiRoot}${path}`, { ...init, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token()}`, ...init?.headers } })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof payload.detail === 'string' ? payload.detail : payload.detail?.code ?? JSON.stringify(payload.detail))
  }
  return response.json() as Promise<T>
}

export function ControllerSettings() {
  const [value, setValue] = useState(token)
  return <Stack direction={{ xs: 'column', sm: 'row' }} gap={2} alignItems="flex-start">
    <TextField fullWidth label="Bearer token" type="password" value={value} onChange={(event) => setValue(event.target.value)} helperText="Stored only in this browser." />
    <Button variant="contained" onClick={() => localStorage.setItem('controller.api.token', value.trim())}>Save</Button>
  </Stack>
}

export function WorkersPage() {
  const [runs, setRuns] = useState<Run[]>([])
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [proxies, setProxies] = useState<Proxy[]>([])
  const [identities, setIdentities] = useState<Identity[]>([])
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [identityHint, setIdentityHint] = useState('')
  const [logRun, setLogRun] = useState<Run | null>(null)
  const [logs, setLogs] = useState('')
  const [mediaDialog, setMediaDialog] = useState<MediaDialog | null>(null)
  const [mediaVideoIndex, setMediaVideoIndex] = useState(0)
  const [mediaAspectRatio, setMediaAspectRatio] = useState(16 / 9)
  const [viewport, setViewport] = useState({ width: window.innerWidth, height: window.innerHeight })
  const [sortColumn, setSortColumn] = useState<SortColumn>('created')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [form, setForm] = useState({ identity: 'test-user-001', scenario: '', priority: 0, debug: false, recording: true, proxy_mode: 'default', proxy_config_id: '', timeout_seconds: 3600 })

  const refresh = useCallback(async () => {
    try {
      const [nextRuns, nextScenarios, nextProxies, nextIdentities] = await Promise.all([api<Run[]>('/runs?limit=10000'), api<Scenario[]>('/scenarios'), api<Proxy[]>('/proxies'), api<Identity[]>('/identities')])
      setRuns(nextRuns); setScenarios(nextScenarios); setProxies(nextProxies); setIdentities(nextIdentities)
      setForm((current) => ({ ...current, scenario: current.scenario || nextScenarios[0]?.name || '', identity: nextIdentities.some((item) => item.identity === current.identity) ? current.identity : nextIdentities[0]?.identity || '' }))
      setError('')
    } catch (err) { setError(err instanceof Error ? err.message : 'Controller unavailable') }
  }, [])
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 5000); return () => window.clearInterval(timer) }, [refresh])
  useEffect(() => {
    const handleResize = () => setViewport({ width: window.innerWidth, height: window.innerHeight })
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  async function createRun() {
    try {
      await api('/runs', { method: 'POST', body: JSON.stringify({ ...form, proxy_config_id: form.proxy_mode === 'selected' ? form.proxy_config_id : null }) })
      setOpen(false); setIdentityHint(''); await refresh()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to create run'
      if (message === 'identity_in_use') setIdentityHint(`Identity ${form.identity} is already active. Create or choose another Identity.`)
      else setError(message)
    }
  }
  async function stop(run: Run) { try { await api(`/runs/${run.id}/stop`, { method: 'POST' }); await refresh() } catch (err) { setError(String(err)) } }
  async function changePriority(run: Run, priority: number) { try { await api(`/runs/${run.id}`, { method: 'PATCH', body: JSON.stringify({ priority }) }); await refresh() } catch (err) { setError(String(err)) } }
  async function showLogs(run: Run) {
    setLogRun(run)
    try { const rows = await api<Array<{ message: string }>>(`/runs/${run.id}/logs?count=1000`); setLogs(rows.map((row) => row.message).join('\n')) }
    catch (err) { setLogs(`Unable to load logs: ${String(err)}`) }
  }
  async function showMedia(run: Run) {
    try {
      const [media, access] = await Promise.all([
        api<RunMedia>(`/runs/${run.id}/media`),
        api<{ ticket: string }>(`/runs/${run.id}/stream-ticket`, { method: 'POST' }),
      ])
      setMediaAspectRatio(16 / 9)
      setMediaVideoIndex(0)
      setMediaDialog({ run, ticket: access.ticket, live: media.live, videos: media.videos })
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to open run media') }
  }
  const stoppable = new Set(['queued', 'allocating', 'starting', 'running', 'waiting_input', 'stopping'])
  function changeSort(column: SortColumn) {
    if (sortColumn === column) setSortDirection((direction) => direction === 'asc' ? 'desc' : 'asc')
    else { setSortColumn(column); setSortDirection(column === 'created' ? 'desc' : 'asc') }
  }
  function sortValue(run: Run, column: SortColumn): string | number {
    if (column === 'scenario') return `${run.scenario_name}:${run.scenario_version}`
    if (column === 'stage') return run.current_stage ?? ''
    if (column === 'created') return new Date(run.created_at).getTime()
    return run[column]
  }
  const sortedRuns = [...runs].sort((left, right) => {
    const leftValue = sortValue(left, sortColumn)
    const rightValue = sortValue(right, sortColumn)
    const result = typeof leftValue === 'number' && typeof rightValue === 'number'
      ? leftValue - rightValue
      : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: 'base' })
    return sortDirection === 'asc' ? result : -result
  })
  const pagination = useClientPagination(sortedRuns, 'workers')
  const sortHeader = (column: SortColumn, label: string) => <TableSortLabel active={sortColumn === column} direction={sortColumn === column ? sortDirection : 'asc'} onClick={() => changeSort(column)}>{label}</TableSortLabel>
  const mediaWidth = Math.max(280, Math.min(viewport.width - 32, (viewport.height - 150) * mediaAspectRatio))
  const selectedVideo = mediaDialog?.videos[mediaVideoIndex]

  function detectNovncAspectRatio(iframe: HTMLIFrameElement) {
    const update = () => {
      const canvas = iframe.contentDocument?.querySelector<HTMLCanvasElement>('#noVNC_canvas')
      if (canvas?.width && canvas.height) setMediaAspectRatio(canvas.width / canvas.height)
    }
    update()
    window.setTimeout(update, 750)
  }

  return <>
    <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2} mb={3}>
      <Box><Typography variant="h4">Workers</Typography><Typography color="text.secondary" mt={.5}>Queue, run history and live execution state.</Typography></Box>
      <Stack direction="row" gap={1}><Button startIcon={<RefreshRounded />} onClick={() => void refresh()}>Refresh</Button><Button variant="contained" startIcon={<AddRounded />} onClick={() => setOpen(true)}>Create run</Button></Stack>
    </Stack>
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}. Configure the Controller token in Settings.</Alert>}
    <Card><CardContent sx={{ overflowX: 'auto' }}><Table size="small" sx={{ minWidth: 900 }}><TableHead><TableRow><TableCell sx={{ whiteSpace: 'nowrap' }}>{sortHeader('identity', 'Identity')}</TableCell><TableCell>{sortHeader('scenario', 'Scenario')}</TableCell><TableCell>{sortHeader('stage', 'Stage')}</TableCell><TableCell>{sortHeader('priority', 'Priority')}</TableCell><TableCell>{sortHeader('created', 'Created')}</TableCell><TableCell align="right">{sortHeader('status', 'Status')}</TableCell></TableRow></TableHead><TableBody>
      {pagination.pageItems.map((run) => { const createdAt = new Date(run.created_at); return <TableRow key={run.id}><TableCell sx={{ whiteSpace: 'nowrap' }}>{run.identity}</TableCell><TableCell><Stack direction="row" alignItems="center" gap={.5}>{run.debug && <Tooltip title="Debug run" enterDelay={600}><BugReportRounded color="warning" sx={{ fontSize: 17 }} /></Tooltip>}<span>{run.scenario_name}:{run.scenario_version}</span></Stack></TableCell><TableCell>{run.current_stage ?? '—'}</TableCell><TableCell>{run.status === 'queued' ? <TextField size="small" type="number" value={run.priority} onChange={(event) => void changePriority(run, Number(event.target.value))} sx={{ width: 80 }} /> : run.priority}</TableCell><TableCell title={createdAt.toISOString()} sx={{ whiteSpace: 'nowrap' }}>{createdTimeFormatter.format(createdAt)}</TableCell><TableCell align="right" sx={{ width: 1, whiteSpace: 'nowrap' }}><Stack direction="row" alignItems="center" justifyContent="flex-end" gap={.5}><Chip size="small" label={run.status} color={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'error' : run.status === 'running' ? 'primary' : 'default'} />{run.live_stream_available && <Tooltip title="Live stream" enterDelay={600}><IconButton size="small" aria-label="Open live stream" onClick={() => void showMedia(run)}><LiveTvRounded fontSize="small" /></IconButton></Tooltip>}{!run.live_stream_available && run.recorded_video_available && <Tooltip title="Recorded video" enterDelay={600}><IconButton size="small" aria-label="Open recorded video" onClick={() => void showMedia(run)}><PlayCircleRounded fontSize="small" /></IconButton></Tooltip>}<Tooltip title="Logs" enterDelay={600}><IconButton size="small" aria-label="Open run logs" onClick={() => void showLogs(run)}><DescriptionRounded fontSize="small" /></IconButton></Tooltip>{stoppable.has(run.status) && <Tooltip title="Stop" enterDelay={600}><IconButton color="error" size="small" aria-label="Stop run" onClick={() => void stop(run)}><StopRounded fontSize="small" /></IconButton></Tooltip>}</Stack></TableCell></TableRow> })}
      {!runs.length && <TableRow><TableCell colSpan={6}><Typography color="text.secondary" textAlign="center" py={4}>No runs yet.</Typography></TableCell></TableRow>}
    </TableBody></Table></CardContent><ClientTablePagination count={runs.length} {...pagination} /></Card>
    <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm"><DialogTitle>Create run</DialogTitle><DialogContent><Stack gap={2} mt={1}>
      {identityHint && <Alert severity="warning">{identityHint}</Alert>}
      <FormControl><InputLabel>Identity</InputLabel><Select label="Identity" value={form.identity} onChange={(e) => setForm({ ...form, identity: e.target.value })}>{identities.map((item) => <MenuItem key={item.identity} value={item.identity} disabled={item.in_use}>{item.identity}{item.in_use ? ' (in use)' : ''}</MenuItem>)}</Select></FormControl>
      <FormControl><InputLabel>Scenario</InputLabel><Select label="Scenario" value={form.scenario} onChange={(e) => setForm({ ...form, scenario: e.target.value })}>{scenarios.map((item) => <MenuItem key={item.id} value={item.name}>{item.name}:{item.version}</MenuItem>)}</Select></FormControl>
      <TextField label="Priority" type="number" value={form.priority} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} />
      <TextField label="Timeout (seconds)" type="number" value={form.timeout_seconds} onChange={(e) => setForm({ ...form, timeout_seconds: Number(e.target.value) })} />
      <FormControl><InputLabel>Proxy</InputLabel><Select label="Proxy" value={form.proxy_mode} onChange={(e) => setForm({ ...form, proxy_mode: e.target.value })}><MenuItem value="default">Identity/default proxy</MenuItem><MenuItem value="disabled">Disabled</MenuItem><MenuItem value="selected">Select configuration</MenuItem></Select></FormControl>
      {form.proxy_mode === 'selected' && <FormControl><InputLabel>Proxy configuration</InputLabel><Select label="Proxy configuration" value={form.proxy_config_id} onChange={(e) => setForm({ ...form, proxy_config_id: e.target.value })}>{proxies.map((item) => <MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>)}</Select></FormControl>}
      <FormControlLabel control={<Switch checked={form.debug} onChange={(e) => setForm({ ...form, debug: e.target.checked, proxy_mode: e.target.checked ? 'disabled' : form.proxy_mode })} />} label="Debug mode" />
      <FormControlLabel control={<Switch checked={form.recording} onChange={(e) => setForm({ ...form, recording: e.target.checked })} />} label="Record video" />
    </Stack></DialogContent><DialogActions><Button onClick={() => setOpen(false)}>Cancel</Button><Button variant="contained" onClick={() => void createRun()} disabled={!form.identity || !form.scenario || (form.proxy_mode === 'selected' && !form.proxy_config_id)}>Create</Button></DialogActions></Dialog>
    <Dialog open={Boolean(logRun)} onClose={() => setLogRun(null)} fullWidth maxWidth="lg"><DialogTitle>Run logs — {logRun?.identity}</DialogTitle><DialogContent><Box component="pre" sx={{ bgcolor: '#0f172a', color: '#e2e8f0', p: 2, borderRadius: 1, minHeight: 320, maxHeight: '60vh', overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 12 }}>{logs || 'No logs available.'}</Box></DialogContent><DialogActions><Button onClick={() => logRun && void showLogs(logRun)}>Refresh</Button><Button onClick={() => setLogRun(null)}>Close</Button></DialogActions></Dialog>
    <Dialog open={Boolean(mediaDialog)} onClose={() => setMediaDialog(null)} maxWidth={false} slotProps={{ paper: { sx: { width: mediaWidth, maxWidth: 'calc(100vw - 16px)', maxHeight: 'calc(100vh - 16px)', m: 1, overflow: 'hidden', transition: 'width 160ms ease' } } }}><DialogTitle>{mediaDialog?.live ? 'Live stream' : 'Recorded video'} — {mediaDialog?.run.identity}</DialogTitle><DialogContent sx={{ p: 1, bgcolor: '#05070a', overflow: 'hidden' }}>
      {mediaDialog?.live && <Box component="iframe" scrolling="no" title="Read-only noVNC stream" onLoad={(event) => detectNovncAspectRatio(event.currentTarget)} src={`${apiRoot}/runs/${mediaDialog.run.id}/novnc/vnc.html?${new URLSearchParams({ autoconnect: 'true', resize: 'scale', view_only: 'true', path: `${apiRoot.slice(1)}/runs/${mediaDialog.run.id}/novnc/websockify?ticket=${encodeURIComponent(mediaDialog.ticket)}`, ticket: mediaDialog.ticket })}`} sx={{ width: '100%', maxHeight: 'calc(100vh - 152px)', aspectRatio: mediaAspectRatio, border: 0, display: 'block', overflow: 'hidden' }} />}
      {!mediaDialog?.live && selectedVideo && <Stack gap={1} sx={{ overflow: 'hidden' }}>
        {mediaDialog.videos.length > 1 && <Select size="small" value={mediaVideoIndex} onChange={(event) => { setMediaAspectRatio(16 / 9); setMediaVideoIndex(Number(event.target.value)) }} sx={{ bgcolor: 'background.paper' }}>{mediaDialog.videos.map((video, index) => <MenuItem key={video.name} value={index}>{video.name}</MenuItem>)}</Select>}
        <Box key={selectedVideo.name} component="video" controls preload="metadata" onLoadedMetadata={(event) => { if (event.currentTarget.videoWidth && event.currentTarget.videoHeight) setMediaAspectRatio(event.currentTarget.videoWidth / event.currentTarget.videoHeight) }} src={`${apiRoot}/runs/${mediaDialog.run.id}/videos/${encodeURIComponent(selectedVideo.name)}?ticket=${encodeURIComponent(mediaDialog.ticket)}`} sx={{ width: '100%', maxHeight: mediaDialog.videos.length > 1 ? 'calc(100vh - 201px)' : 'calc(100vh - 152px)', objectFit: 'contain', bgcolor: '#000', display: 'block' }} />
      </Stack>}
    </DialogContent><DialogActions><Button onClick={() => setMediaDialog(null)}>Close</Button></DialogActions></Dialog>
  </>
}
