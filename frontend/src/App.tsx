import { MouseEvent, useEffect, useLayoutEffect, useRef } from 'react'
import './styles/theme.css'
import './navigation/navigation.css'
import NavBar from './components/NavBar'
import SearchScreen from './components/SearchScreen'
import HowItWorksPage from './components/HowItWorksPage'
import AboutPage from './components/AboutPage'
import { useClaimChecker } from './hooks/useClaimChecker'
import { useTheme } from './hooks/useTheme'
import { Page, PageLink, ROUTES } from './navigation/routes'
import { usePageNavigation } from './navigation/usePageNavigation'

function App() {
  const checker = useClaimChecker()
  const { theme, toggleTheme } = useTheme()
  const { page, revision, navigate } = usePageNavigation()
  const mainRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const previous = window.history.scrollRestoration
    window.history.scrollRestoration = 'manual'
    return () => { window.history.scrollRestoration = previous }
  }, [])

  useLayoutEffect(() => {
    document.title = page === 'not-found' ? 'Page not found | Second Opinion' : ROUTES[page].title
  }, [page])

  useEffect(() => {
    // On initial entry retain the browser's normal focus and fragment behavior.
    // Later SPA transitions need an explicit destination for keyboard users.
    if (revision === 0) return
    const heading = mainRef.current?.querySelector('h1')
    const target = heading ?? mainRef.current
    if (target) {
      target.tabIndex = -1
      target.focus({ preventScroll: true })
    }
    // Run after child effects, including a restored result's automatic scroll.
    window.scrollTo(0, 0)
  }, [page, revision])

  function skipToContent(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    mainRef.current?.focus({ preventScroll: true })
    mainRef.current?.scrollIntoView({ block: 'start' })
  }

  function goHome() {
    checker.reset()
    navigate('home')
  }

  function goToPage(next: Page) {
    if (next === 'home') goHome()
    else navigate(next)
  }

  return (
    <div className="page" data-theme={theme}>
      <a className="skip-link" href="#main-content" onClick={skipToContent}>Skip to content</a>
      <NavBar
        current={page}
        theme={theme}
        onToggleTheme={toggleTheme}
        onNavigate={goToPage}
      />

      <main id="main-content" ref={mainRef} tabIndex={-1}>
        {page === 'how-it-works' && <HowItWorksPage onTryIt={goHome} />}
        {page === 'about' && <AboutPage />}
        {page === 'home' && (
          <SearchScreen
            pmcOnly={checker.pmcOnly}
            setPmcOnly={checker.setPmcOnly}
            claim={checker.claim}
            setClaim={checker.setClaim}
            status={checker.status}
            errorMessage={checker.errorMessage}
            checkClaim={checker.checkClaim}
            verdict={checker.verdict}
            candidates={checker.candidates}
            activeClaim={checker.activeClaim}
            onHowItWorks={() => navigate('how-it-works')}
          />
        )}
        {page === 'not-found' && (
          <section className="route-not-found">
            <h1>Page not found</h1>
            <p>This address does not match a Second Opinion page.</p>
            <PageLink page="home" onNavigate={goToPage}>Go to the home page</PageLink>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
