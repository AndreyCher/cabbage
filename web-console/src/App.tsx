import { useCallback, useEffect, useState } from 'react'
import {
  AppBar, Avatar, Box, Button, Card, CardContent, Chip, Divider, Drawer,
  IconButton, LinearProgress, List, ListItemButton, ListItemIcon, ListItemText,
  Stack, ToggleButton, ToggleButtonGroup, Toolbar, Tooltip, Typography,
} from '@mui/material'
import {
  AppsRounded, CheckCircleRounded, CloudQueueRounded, DashboardRounded,
  ChevronLeftRounded, ChevronRightRounded, ComputerRounded, DarkModeRounded,
  DataObjectRounded, LightModeRounded, MenuRounded, PlayArrowRounded,
  RefreshRounded, SettingsRounded, StorageRounded, WebRounded,
} from '@mui/icons-material'
import { consoleModules } from './modules/registry'
import { useThemeMode } from './theme'

type Health = { status?: string; component?: string; version?: string }
type RegistryComponent = {
  enabled: boolean
  type: string
  display_name: string
  description: string
  api: { base_url: string; health_path?: string; console_proxy_path?: string; version?: string }
}
type Registry = { schema_version: number; components: Record<string, RegistryComponent> }
type Service = RegistryComponent & {
  id: string
  name: string
  endpoint: string
  icon: typeof DataObjectRounded
  accent: string
}

const drawerWidth = 248
const collapsedDrawerWidth = 72
const pageIds = new Set([...consoleModules.flatMap((module) => module.pages ?? []).map((page) => page.id), 'settings'])
const fullWidthTablePages = new Set(['workers', 'identities', 'scenarios'])

function pageFromLocation() {
  const page = decodeURIComponent(window.location.hash.replace(/^#\/?/, ''))
  return pageIds.has(page) ? page : 'overview'
}

const presentation: Record<string, { icon: typeof DataObjectRounded; accent: string }> = {
  worker: { icon: WebRounded, accent: '#ea580c' },
  'data-provider': { icon: StorageRounded, accent: '#7c3aed' },
  frontend: { icon: DashboardRounded, accent: '#1769e0' },
  controller: { icon: CloudQueueRounded, accent: '#0891b2' },
}

function App() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('cabbage.sidebar.collapsed') === 'true')
  const [activePage, setActivePage] = useState(pageFromLocation)
  const [loading, setLoading] = useState(true)
  const [health, setHealth] = useState<Record<string, Health | null>>({})
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const [services, setServices] = useState<Service[]>([])
  const [registryError, setRegistryError] = useState(false)
  const { preference, setPreference } = useThemeMode()
  const pages = consoleModules.flatMap((module) => module.pages ?? [])
  const settingsSections = consoleModules.flatMap((module) => module.settings ?? [])
  const fullWidthTablePage = fullWidthTablePages.has(activePage)
  const desktopWidth = collapsed ? collapsedDrawerWidth : drawerWidth
  const selectPage = (id: string) => {
    setActivePage(id)
    setMobileOpen(false)
    if (window.location.hash !== `#/${id}`) window.history.pushState(null, '', `#/${id}`)
  }
  const toggleCollapsed = () => setCollapsed((value) => {
    localStorage.setItem('cabbage.sidebar.collapsed', String(!value))
    return !value
  })

  const refresh = useCallback(async () => {
    setLoading(true)
    let configured: Service[] = []
    try {
      const registryResponse = await fetch('/runtime/components.json', { cache: 'no-store' })
      if (!registryResponse.ok) throw new Error(String(registryResponse.status))
      const registry = await registryResponse.json() as Registry
      configured = Object.entries(registry.components)
        .filter(([, component]) => component.enabled && component.api.health_path && component.api.console_proxy_path)
        .map(([id, component]) => ({
          ...component,
          id,
          name: component.display_name,
          endpoint: `${component.api.console_proxy_path}${component.api.health_path}`,
          ...(presentation[component.type] ?? { icon: AppsRounded, accent: '#64748b' }),
        }))
      setServices(configured)
      setRegistryError(false)
    } catch {
      setRegistryError(true)
    }
    const entries = await Promise.all(configured.map(async (service) => {
      try {
        const response = await fetch(service.endpoint, { signal: AbortSignal.timeout(3500) })
        if (!response.ok) throw new Error(String(response.status))
        return [service.name, await response.json()] as const
      } catch {
        return [service.name, null] as const
      }
    }))
    setHealth(Object.fromEntries(entries))
    setUpdatedAt(new Date())
    setLoading(false)
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    const restorePage = () => setActivePage(pageFromLocation())
    window.addEventListener('hashchange', restorePage)
    window.addEventListener('popstate', restorePage)
    return () => {
      window.removeEventListener('hashchange', restorePage)
      window.removeEventListener('popstate', restorePage)
    }
  }, [])

  const navigation = (compact = false) => (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Toolbar sx={{ px: compact ? 2.25 : 2.5, gap: 1.5, overflow: 'hidden' }}>
        <Avatar variant="rounded" sx={{ bgcolor: '#1769e0', width: 34, height: 34 }}>C</Avatar>
        {!compact && <Box sx={{ whiteSpace: 'nowrap' }}><Typography fontWeight={800}>Cabbage</Typography><Typography variant="caption" color="text.secondary">Control plane</Typography></Box>}
      </Toolbar>
      <Divider />
      <List sx={{ px: compact ? 1 : 1.5, py: 2 }}>
        {pages.map((page) => {
          const { id, label, icon: Icon } = page
          return <Tooltip key={id} title={compact ? label : ''} placement="right">
            <ListItemButton onClick={() => selectPage(id)} selected={activePage === id} sx={{ borderRadius: 2, mb: .5, minHeight: 44, pl: compact ? 2 : page.parentId ? 4 : 2, justifyContent: compact ? 'center' : 'initial' }}>
              <ListItemIcon sx={{ minWidth: compact ? 0 : 38, justifyContent: 'center' }}><Icon fontSize="small" /></ListItemIcon>
              {!compact && <ListItemText primary={label} primaryTypographyProps={{ fontSize: 14, fontWeight: activePage === id ? 700 : 500 }} />}
            </ListItemButton>
          </Tooltip>
        })}
      </List>
      <Box sx={{ mt: 'auto', p: 1.5 }}>
        <Tooltip title={compact ? 'Settings' : ''} placement="right"><ListItemButton selected={activePage === 'settings'} onClick={() => selectPage('settings')} sx={{ borderRadius: 2, justifyContent: compact ? 'center' : 'initial' }}><ListItemIcon sx={{ minWidth: compact ? 0 : 38, justifyContent: 'center' }}><SettingsRounded fontSize="small" /></ListItemIcon>{!compact && <ListItemText primary="Settings" />}</ListItemButton></Tooltip>
        <Tooltip title={compact ? 'Expand menu' : 'Collapse menu'} placement="right"><ListItemButton onClick={toggleCollapsed} sx={{ display: { xs: 'none', md: 'flex' }, borderRadius: 2, mt: .5, justifyContent: compact ? 'center' : 'initial' }}><ListItemIcon sx={{ minWidth: compact ? 0 : 38, justifyContent: 'center' }}>{compact ? <ChevronRightRounded /> : <ChevronLeftRounded />}</ListItemIcon>{!compact && <ListItemText primary="Collapse" />}</ListItemButton></Tooltip>
      </Box>
    </Box>
  )

  const online = services.filter((service) => health[service.name]?.status === 'ok').length

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppBar position="fixed" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider', ml: { md: `${desktopWidth}px` }, width: { md: `calc(100% - ${desktopWidth}px)` }, transition: 'width 180ms, margin 180ms' }}>
        <Toolbar>
          <IconButton onClick={() => setMobileOpen(true)} sx={{ display: { md: 'none' }, mr: 1 }}><MenuRounded /></IconButton>
          <Typography fontWeight={700}>{activePage === 'settings' ? 'Settings' : pages.find((page) => page.id === activePage)?.label}</Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Tooltip title="Refresh health"><IconButton onClick={() => void refresh()}><RefreshRounded /></IconButton></Tooltip>
          <Avatar sx={{ ml: 1.5, width: 34, height: 34, bgcolor: '#dbeafe', color: '#1769e0', fontSize: 14 }}>BB</Avatar>
        </Toolbar>
        {loading && <LinearProgress />}
      </AppBar>
      <Box component="nav" sx={{ width: { md: desktopWidth }, flexShrink: { md: 0 }, transition: 'width 180ms' }}>
        <Drawer variant="temporary" open={mobileOpen} onClose={() => setMobileOpen(false)} ModalProps={{ keepMounted: true }} sx={{ display: { xs: 'block', md: 'none' }, '& .MuiDrawer-paper': { width: drawerWidth } }}>{navigation()}</Drawer>
        <Drawer variant="permanent" open sx={{ display: { xs: 'none', md: 'block' }, '& .MuiDrawer-paper': { width: desktopWidth, boxSizing: 'border-box', overflowX: 'hidden', transition: 'width 180ms' } }}>{navigation(collapsed)}</Drawer>
      </Box>
      <Box component="main" sx={{ flexGrow: 1, minWidth: 0, p: fullWidthTablePage ? 1.5 : { xs: 2, sm: 3, lg: 4 }, width: { md: `calc(100% - ${desktopWidth}px)` }, mt: 8, transition: 'width 180ms' }}>
        <Box sx={{ width: '100%', maxWidth: fullWidthTablePage ? 'none' : 1240, mx: fullWidthTablePage ? 0 : 'auto' }}>
          {activePage === 'settings' ? <>
            <Typography variant="h4">Settings</Typography><Typography color="text.secondary" mt={.5} mb={4}>Configure the console and installed modules.</Typography>
            <Card><CardContent sx={{ p: 3 }}><Typography variant="h6">Appearance</Typography><Typography variant="body2" color="text.secondary" mt={.5} mb={2}>Choose a theme or follow your operating system.</Typography>
              <ToggleButtonGroup exclusive value={preference} onChange={(_, value) => value && setPreference(value)} aria-label="Color theme">
                <ToggleButton value="system"><ComputerRounded sx={{ mr: 1 }} />System</ToggleButton><ToggleButton value="light"><LightModeRounded sx={{ mr: 1 }} />Light</ToggleButton><ToggleButton value="dark"><DarkModeRounded sx={{ mr: 1 }} />Dark</ToggleButton>
              </ToggleButtonGroup>
            </CardContent></Card>
            {settingsSections.map(({ id, title, component: Section }) => <Card key={id} sx={{ mt: 2 }}><CardContent sx={{ p: 3 }}><Typography variant="h6" mb={2}>{title}</Typography><Section /></CardContent></Card>)}
          </> : activePage !== 'overview' ? (() => { const Page = pages.find((page) => page.id === activePage)?.component; return Page ? <Page /> : null })() : <>
          <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2} mb={4}>
            <Box><Typography variant="h4">System overview</Typography><Typography color="text.secondary" mt={.5}>Operate workers, scenarios and their data sources.</Typography></Box>
            <Button onClick={() => selectPage('workers')} variant="contained" startIcon={<PlayArrowRounded />} sx={{ alignSelf: { xs: 'stretch', sm: 'center' } }}>Create run</Button>
          </Stack>
          {registryError && <Card sx={{ mb: 3, borderColor: '#f59e0b' }}><CardContent><Typography color="warning.main">Component registry is unavailable. Check `/runtime/components.json`.</Typography></CardContent></Card>}

          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' }, gap: 2, mb: 4 }}>
            {[
              ['Healthy services', `${online}/${services.length}`, CheckCircleRounded, '#16a34a'],
              ['Active workers', services.filter((service) => service.type === 'worker' && health[service.name]?.status === 'ok').length.toString(), CloudQueueRounded, '#1769e0'],
              ['Data backends', services.filter((service) => service.type === 'data-provider' && health[service.name]?.status === 'ok').length.toString(), DataObjectRounded, '#7c3aed'],
            ].map(([label, value, Icon, color]) => (
              <Card key={label as string}><CardContent><Stack direction="row" justifyContent="space-between"><Box><Typography variant="body2" color="text.secondary">{label as string}</Typography><Typography variant="h4" mt={1}>{value as string}</Typography></Box><Avatar sx={{ bgcolor: `${color}18`, color: color as string }}><Icon /></Avatar></Stack></CardContent></Card>
            ))}
          </Box>

          <Typography variant="h6" mb={2}>Components</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, 1fr)' }, gap: 2 }}>
            {services.map((service) => {
              const state = health[service.name]
              const isOnline = state?.status === 'ok'
              const Icon = service.icon
              return <Card key={service.name}><CardContent sx={{ p: 3 }}>
                <Stack direction="row" alignItems="flex-start" gap={2}>
                  <Avatar variant="rounded" sx={{ bgcolor: `${service.accent}16`, color: service.accent }}><Icon /></Avatar>
                  <Box sx={{ flexGrow: 1 }}><Stack direction="row" justifyContent="space-between" alignItems="center" gap={1}><Typography variant="h6">{service.name}</Typography><Chip size="small" label={isOnline ? 'Healthy' : 'Offline'} color={isOnline ? 'success' : 'default'} variant={isOnline ? 'filled' : 'outlined'} /></Stack><Typography variant="body2" color="text.secondary" mt={.5}>{service.description}</Typography><Stack direction="row" gap={2} mt={2}><Typography variant="caption" color="text.secondary">Version <b>{state?.version ?? '—'}</b></Typography><Typography variant="caption" color="text.secondary">Component <b>{state?.component ?? '—'}</b></Typography></Stack></Box>
                </Stack>
              </CardContent>
              </Card>
            })}
          </Box>
          <Typography variant="caption" color="text.secondary" display="block" mt={2}>Last checked: {updatedAt?.toLocaleTimeString() ?? '—'}</Typography>
          </>}
        </Box>
      </Box>
    </Box>
  )
}

export default App
