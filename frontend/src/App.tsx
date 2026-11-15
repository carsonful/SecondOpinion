import { useEffect } from 'react'
import './styles/theme.css'
import NavBar from './components/NavBar'
import SearchScreen from './components/SearchScreen'
import HowItWorksPage from './components/HowItWorksPage'
import AboutPage from './components/AboutPage'
import { useClaimChecker } from './hooks/useClaimChecker'
import { useTheme } from './hooks/useTheme'
import { Page, PageLink } from './navigation/routes'
import { usePageNavigation } from './navigation/usePageNavigation'

function App() {
  const checker = useClaimChecker()
  const { theme, toggleTheme } = useTheme()
  const { page, navigate } = usePageNavigation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [page])

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
      <NavBar
        current={page}
        theme={theme}
        onToggleTheme={toggleTheme}
        onNavigate={goToPage}
      />

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
    </div>
  )
}

export default App
