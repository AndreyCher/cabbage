import { AppsRounded, DashboardRounded, DataObjectRounded, RouteRounded } from '@mui/icons-material'
import { Typography } from '@mui/material'
import type { ConsoleModule } from './types'

function Placeholder({ title }: { title: string }) {
  return <><Typography variant="h4">{title}</Typography><Typography color="text.secondary" mt={1}>This module is ready for its component-specific interface.</Typography></>
}

// Add a module to this registry to contribute pages, navigation and settings.
export const consoleModules: ConsoleModule[] = [
  { id: 'overview', pages: [{ id: 'overview', label: 'Overview', icon: DashboardRounded, component: () => <Placeholder title="Overview" /> }] },
  { id: 'workers', pages: [{ id: 'workers', label: 'Workers', icon: AppsRounded, component: () => <Placeholder title="Workers" /> }] },
  { id: 'data-sources', pages: [{ id: 'data-sources', label: 'Data sources', icon: DataObjectRounded, component: () => <Placeholder title="Data sources" /> }] },
  { id: 'scenarios', pages: [{ id: 'scenarios', label: 'Scenarios', icon: RouteRounded, component: () => <Placeholder title="Scenarios" /> }] },
]
