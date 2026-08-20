import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { CssBaseline, ThemeProvider, createTheme, useMediaQuery } from '@mui/material'

export type ThemePreference = 'system' | 'light' | 'dark'

type ThemeContextValue = {
  preference: ThemePreference
  resolvedMode: 'light' | 'dark'
  setPreference: (preference: ThemePreference) => void
}

const ThemeModeContext = createContext<ThemeContextValue | null>(null)

export function useThemeMode() {
  const value = useContext(ThemeModeContext)
  if (!value) throw new Error('useThemeMode must be used inside AppThemeProvider')
  return value
}

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const systemDark = useMediaQuery('(prefers-color-scheme: dark)')
  const [preference, setPreferenceState] = useState<ThemePreference>(() => {
    const saved = localStorage.getItem('cabbage.theme')
    return saved === 'light' || saved === 'dark' ? saved : 'system'
  })
  const resolvedMode = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference
  const setPreference = (value: ThemePreference) => {
    localStorage.setItem('cabbage.theme', value)
    setPreferenceState(value)
  }
  const theme = useMemo(() => createTheme({
    palette: {
      mode: resolvedMode,
      primary: { main: resolvedMode === 'dark' ? '#3794ff' : '#1769e0' },
      background: resolvedMode === 'dark'
        ? { default: '#1e1e1e', paper: '#252526' }
        : { default: '#f6f8fb', paper: '#ffffff' },
      text: resolvedMode === 'dark'
        ? { primary: '#e7e7e7', secondary: '#a6a6a6' }
        : { primary: '#152033', secondary: '#657289' },
    },
    shape: { borderRadius: 12 },
    typography: {
      fontFamily: 'Inter, Roboto, Arial, sans-serif',
      h4: { fontWeight: 700, fontSize: '1.65rem', lineHeight: 1.25, letterSpacing: '-0.02em' },
      h6: { fontWeight: 700, fontSize: '1.05rem' },
      button: { textTransform: 'none', fontWeight: 600 },
    },
    components: {
      MuiCard: { styleOverrides: { root: { backgroundImage: 'none', border: `1px solid ${resolvedMode === 'dark' ? '#3c3c3c' : '#e5eaf2'}`, boxShadow: resolvedMode === 'dark' ? 'none' : '0 2px 8px rgba(21,32,51,.04)' } } },
      MuiDrawer: { styleOverrides: { paper: { backgroundImage: 'none', backgroundColor: resolvedMode === 'dark' ? '#181818' : '#ffffff' } } },
      MuiAppBar: { styleOverrides: { root: { backgroundImage: 'none', backgroundColor: resolvedMode === 'dark' ? '#181818' : '#ffffff' } } },
      MuiButton: { defaultProps: { disableElevation: true } },
    },
  }), [resolvedMode])

  useEffect(() => {
    document.documentElement.style.colorScheme = resolvedMode
  }, [resolvedMode])

  return <ThemeModeContext.Provider value={{ preference, resolvedMode, setPreference }}>
    <ThemeProvider theme={theme}><CssBaseline />{children}</ThemeProvider>
  </ThemeModeContext.Provider>
}
