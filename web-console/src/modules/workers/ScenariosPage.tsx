import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions,
  DialogContent, DialogTitle, IconButton, Stack, Table, TableBody, TableCell, TableHead,
  TableRow, TextField, Tooltip, Typography,
} from '@mui/material'
import { AddRounded, ContentCopyRounded, DeleteOutlineRounded, EditRounded, FileUploadRounded, RefreshRounded, RemoveRounded, RestoreRounded } from '@mui/icons-material'
import { controllerApi } from './controllerApi'
import { ClientTablePagination, useClientPagination } from '../../components/ClientTablePagination'

type Scenario = {
  id: string
  name: string
  version: number
  definition: Record<string, unknown>
  active: boolean
  deleted: boolean
  created_at: string
  run_count: number
}

export function ScenariosPage() {
  const [items, setItems] = useState<Scenario[]>([])
  const [selected, setSelected] = useState<Scenario | null>(null)
  const [name, setName] = useState('')
  const [json, setJson] = useState('')
  const [error, setError] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<Scenario | null>(null)
  const [cloneSource, setCloneSource] = useState<Scenario | null>(null)
  const [cloneStep, setCloneStep] = useState<'confirm' | 'name' | null>(null)
  const [cloneName, setCloneName] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const fileRef = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    try { setItems(await controllerApi<Scenario[]>('/scenarios?include_archived=true')); setError('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load scenarios') }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  function open(item: Scenario) {
    setSelected(item); setName(item.name); setJson(JSON.stringify(item.definition, null, 2)); setError('')
  }
  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    try {
      const definition = JSON.parse(await file.text()) as Record<string, unknown>
      if (!definition || Array.isArray(definition) || typeof definition !== 'object') throw new Error('Scenario file must contain a JSON object')
      if (!Array.isArray(definition.actions)) throw new Error('Scenario must contain an actions array')
      const importedName = typeof definition.name === 'string' && definition.name ? definition.name : file.name.replace(/\.json$/i, '')
      setSelected({ id: '', name: importedName, version: 0, definition, active: false, deleted: false, created_at: '', run_count: 0 })
      setName(importedName); setJson(JSON.stringify({ ...definition, name: importedName }, null, 2)); setError('')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to import scenario') }
  }
  async function save() {
    try {
      const definition = JSON.parse(json) as Record<string, unknown>
      if (!definition || Array.isArray(definition) || typeof definition !== 'object') throw new Error('Scenario must be a JSON object')
      if (!Array.isArray(definition.actions)) throw new Error('Scenario must contain an actions array')
      definition.name = name
      await controllerApi('/scenarios', { method: 'POST', body: JSON.stringify({ name, definition }) })
      setSelected(null); await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save scenario') }
  }
  async function remove() {
    if (!deleteTarget) return
    try {
      await controllerApi(`/scenarios/${encodeURIComponent(deleteTarget.name)}`, { method: 'DELETE' })
      setDeleteTarget(null); await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete scenario') }
  }
  async function activate(item: Scenario) {
    try {
      await controllerApi(`/scenarios/versions/${item.id}/activate`, { method: 'POST' })
      await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to activate scenario version') }
  }
  async function cloneScenario() {
    if (!cloneSource || !cloneName.trim()) return
    try {
      await controllerApi(`/scenarios/versions/${cloneSource.id}/clone`, { method: 'POST', body: JSON.stringify({ name: cloneName.trim() }) })
      setCloneSource(null); setCloneStep(null); setCloneName(''); await refresh()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to clone scenario'
      setError(message.includes('scenario_name_exists') ? 'A scenario with this name already exists. Choose another name.' : message)
    }
  }
  function beginClone(item: Scenario) {
    setCloneSource(item); setCloneName(''); setCloneStep('confirm'); setError('')
  }
  const groups = Object.values(items.reduce<Record<string, Scenario[]>>((result, item) => {
    ;(result[item.name] ??= []).push(item)
    return result
  }, {})).map((versions) => versions.sort((a, b) => b.version - a.version))
  const pagination = useClientPagination(groups, 'scenarios')
  function toggle(name: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(name)) next.delete(name); else next.add(name)
      return next
    })
  }

  return <>
    <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2} mb={3}>
      <Box><Typography variant="h4">Scenarios</Typography><Typography color="text.secondary" mt={.5}>Versioned scenario templates. Saving creates a new active version.</Typography></Box>
      <Stack direction="row" gap={1}><Button startIcon={<RefreshRounded />} onClick={() => void refresh()}>Refresh</Button><Button variant="contained" startIcon={<FileUploadRounded />} onClick={() => fileRef.current?.click()}>Import scenario</Button><input ref={fileRef} hidden type="file" accept="application/json,.json" onChange={(event) => void importFile(event)} /></Stack>
    </Stack>
    {error && !selected && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    <Card><CardContent sx={{ overflowX: 'auto' }}><Table><TableHead><TableRow><TableCell width={52} /><TableCell>Name</TableCell><TableCell>Version</TableCell><TableCell>Steps</TableCell><TableCell>Runs</TableCell><TableCell>Status</TableCell><TableCell>Created</TableCell><TableCell /></TableRow></TableHead><TableBody>
      {pagination.pageItems.flatMap((versions) => {
        const active = versions.find((item) => item.active) ?? versions[0]
        const isExpanded = expanded.has(active.name)
        const archived = versions.filter((item) => item.id !== active.id)
        const ordered = [active, ...archived]
        const visible = isExpanded ? ordered : [active]
        const latestVersion = Math.max(...versions.map((item) => item.version))
        return visible.map((item, index) => <TableRow key={item.id} sx={{ bgcolor: item.active ? 'action.hover' : undefined }}>
          <TableCell>{index === 0 && <Tooltip title={isExpanded ? 'Collapse versions' : 'Expand versions'} enterDelay={600}><IconButton size="small" onClick={() => toggle(active.name)} aria-label={isExpanded ? 'Collapse versions' : 'Expand versions'}>{isExpanded ? <RemoveRounded /> : <AddRounded />}</IconButton></Tooltip>}</TableCell>
          <TableCell><Typography fontWeight={item.active ? 700 : 500} sx={{ pl: isExpanded && index > 0 ? 2 : 0 }}>{item.name}</Typography>{index === 0 && versions.length > 1 && <Typography variant="caption" color="text.secondary">{versions.length} versions · latest v{latestVersion} · active v{active.version}</Typography>}</TableCell>
          <TableCell>v{item.version}</TableCell><TableCell>{Array.isArray(item.definition.actions) ? item.definition.actions.length : 0}</TableCell><TableCell>{item.run_count}</TableCell>
          <TableCell><Chip size="small" label={item.active ? 'Active' : 'Archived'} color={item.active ? 'success' : 'default'} variant="outlined" /></TableCell>
          <TableCell>{new Date(item.created_at).toLocaleString()}</TableCell><TableCell align="right"><Stack direction="row" justifyContent="flex-end" gap={.5}>{item.active && <Tooltip title="Open" enterDelay={600}><IconButton size="small" aria-label="Open scenario" onClick={() => open(item)}><EditRounded /></IconButton></Tooltip>}<Tooltip title="Clone" enterDelay={600}><IconButton size="small" aria-label="Clone scenario" onClick={() => beginClone(item)}><ContentCopyRounded /></IconButton></Tooltip>{!item.active && <Tooltip title="Activate" enterDelay={600}><IconButton size="small" color="primary" aria-label="Activate scenario version" onClick={() => void activate(item)}><RestoreRounded /></IconButton></Tooltip>}{item.active && <Tooltip title="Delete" enterDelay={600}><IconButton size="small" color="error" aria-label="Delete scenario" onClick={() => { setDeleteTarget(item); setError('') }}><DeleteOutlineRounded /></IconButton></Tooltip>}</Stack></TableCell>
        </TableRow>)
      })}
      {!groups.length && <TableRow><TableCell colSpan={8}><Typography color="text.secondary" textAlign="center" py={4}>No scenarios.</Typography></TableCell></TableRow>}
    </TableBody></Table></CardContent><ClientTablePagination count={groups.length} {...pagination} /></Card>
    <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} fullWidth maxWidth="md"><DialogTitle>{selected?.version ? `Edit ${name} v${selected.version}` : 'Import scenario'}</DialogTitle><DialogContent><Stack gap={2} mt={1}>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="Scenario name" value={name} onChange={(event) => setName(event.target.value)} required />
      <TextField label="Scenario JSON" value={json} onChange={(event) => setJson(event.target.value)} multiline minRows={20} maxRows={32} InputProps={{ sx: { fontFamily: 'monospace', fontSize: 13 } }} />
      {selected?.version ? <Alert severity="info">Saving preserves v{selected.version} and creates a new active version.</Alert> : null}
    </Stack></DialogContent><DialogActions><Button onClick={() => setSelected(null)}>Cancel</Button><Button variant="contained" onClick={() => void save()} disabled={!name.trim() || !json.trim()}>Save new version</Button></DialogActions></Dialog>
    <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} maxWidth="sm" fullWidth><DialogTitle>Delete scenario {deleteTarget?.name}?</DialogTitle><DialogContent><Alert severity="warning" sx={{ mt: 1 }}>The scenario and all its versions will disappear from Create Run and the scenario list. Historical run records remain intact.</Alert>{error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}</DialogContent><DialogActions><Button onClick={() => setDeleteTarget(null)}>Cancel</Button><Button color="error" variant="contained" onClick={() => void remove()}>Delete scenario</Button></DialogActions></Dialog>
    <Dialog open={cloneStep === 'confirm'} onClose={() => { setCloneSource(null); setCloneStep(null) }} maxWidth="sm" fullWidth><DialogTitle>Clone {cloneSource?.name} v{cloneSource?.version}?</DialogTitle><DialogContent><Typography sx={{ mt: 1 }}>A new independent scenario will be created from this version. The original and its version history will remain unchanged.</Typography></DialogContent><DialogActions><Button onClick={() => { setCloneSource(null); setCloneStep(null) }}>Cancel</Button><Button variant="contained" onClick={() => setCloneStep('name')}>Continue</Button></DialogActions></Dialog>
    <Dialog open={cloneStep === 'name'} onClose={() => { setCloneSource(null); setCloneStep(null) }} maxWidth="sm" fullWidth><DialogTitle>Name the cloned scenario</DialogTitle><DialogContent><Stack gap={2} mt={1}>{error && <Alert severity="error">{error}</Alert>}<TextField autoFocus label="New scenario name" value={cloneName} onChange={(event) => { setCloneName(event.target.value); setError('') }} helperText="The name must be unique and may contain letters, numbers, dots, underscores, and hyphens." required /></Stack></DialogContent><DialogActions><Button onClick={() => { setCloneSource(null); setCloneStep(null) }}>Cancel</Button><Button variant="contained" startIcon={<ContentCopyRounded />} disabled={!cloneName.trim()} onClick={() => void cloneScenario()}>Clone scenario</Button></DialogActions></Dialog>
  </>
}
