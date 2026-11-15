import { useCallback, useEffect, useState } from 'react'
import { Page, ROUTES, pageAt } from './routes'

export function usePageNavigation() {
  const [location, setLocation] = useState(() => ({
    pathname: window.location.pathname,
    revision: 0,
  }))

  useEffect(() => {
    function readHistory() {
      setLocation(previous => previous.pathname === window.location.pathname
        ? previous
        : { pathname: window.location.pathname, revision: previous.revision + 1 })
    }
    window.addEventListener('popstate', readHistory)
    return () => window.removeEventListener('popstate', readHistory)
  }, [])

  const navigate = useCallback((page: Page) => {
    const path = ROUTES[page].path
    if (`${window.location.pathname}${window.location.search}${window.location.hash}` !== path) {
      window.history.pushState(null, '', path)
    }
    setLocation(previous => ({ pathname: path, revision: previous.revision + 1 }))
  }, [])

  return { page: pageAt(location.pathname), revision: location.revision, navigate }
}
