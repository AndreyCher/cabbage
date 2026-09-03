import { AppsRounded, DashboardRounded, DataObjectRounded, PersonRounded, RouteRounded, VpnLockRounded } from '@mui/icons-material'
import { Typography } from '@mui/material'
import type { ConsoleModule } from './types'
import { WorkersPage, ControllerSettings } from './workers/WorkersPage'
import { IdentitiesPage } from './workers/IdentitiesPage'
import { ScenariosPage } from './workers/ScenariosPage'
import { DefaultIdentitySettings } from './workers/DefaultIdentitySettings'
import { ProxiesPage } from './workers/ProxiesPage'
import { WorkerDefaultsSettings } from './workers/WorkerDefaultsSettings'

function Placeholder({ title }: { title: string }) {
  return <><Typography variant="h4">{title}</Typography><Typography color="text.secondary" mt={1}>This module is ready for its component-specific interface.</Typography></>
}

// Add a module to this registry to contribute pages, navigation and settings.
export const consoleModules: ConsoleModule[] = [
  { id: 'overview', pages: [{ id: 'overview', label: 'Overview', icon: DashboardRounded, component: () => <Placeholder title="Overview" /> }] },
  { id: 'workers', pages: [
    { id: 'workers', label: 'Workers', icon: AppsRounded, component: WorkersPage },
    { id: 'identities', label: 'Identities', icon: PersonRounded, component: IdentitiesPage, parentId: 'workers' },
    { id: 'scenarios', label: 'Scenarios', icon: RouteRounded, component: ScenariosPage, parentId: 'workers' },
    { id: 'proxies', label: 'Proxies', icon: VpnLockRounded, component: ProxiesPage, parentId: 'workers' },
  ], settings: [
    { id: 'controller-auth', title: 'Controller API', component: ControllerSettings },
    { id: 'worker-defaults', title: 'Global worker defaults', component: WorkerDefaultsSettings },
    { id: 'identity-defaults', title: 'Default Identity profile', component: DefaultIdentitySettings },
  ] },
  { id: 'data-sources', pages: [{ id: 'data-sources', label: 'Data sources', icon: DataObjectRounded, component: () => <Placeholder title="Data sources" /> }] },
]
