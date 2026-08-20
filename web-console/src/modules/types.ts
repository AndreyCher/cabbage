import type { ComponentType } from 'react'
import type { SvgIconProps } from '@mui/material'

export type ConsolePage = { id: string; label: string; icon: ComponentType<SvgIconProps>; component: ComponentType }
export type SettingsSection = { id: string; title: string; component: ComponentType }
export type ConsoleModule = {
  id: string
  pages?: ConsolePage[]
  settings?: SettingsSection[]
}
