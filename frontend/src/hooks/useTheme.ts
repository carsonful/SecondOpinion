import { useEffect, useState } from 'react'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'so-theme'

function readStored(): Theme {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY)
    if (v === 'light' || v === 'dark') return v
  } catch {
    // storage blocked (private mode etc.): fall back to the default
  }
  return 'dark' // dark is the default look from the Figma
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readStored)

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // ignore
    }
  }, [theme])

  function toggleTheme() {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }

  return { theme, toggleTheme }
}