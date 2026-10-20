import { useEffect, useState } from 'react'
import './styles/theme.css'
import NavBar, { Page } from './components/NavBar'
import SearchScreen from './components/SearchScreen'
import HowItWorksPage from './components/HowItWorksPage'
import AboutPage from './components/AboutPage'
import { useClaimChecker } from './hooks/useClaimChecker'
import { useTheme } from './hooks/useTheme'

function App() {
  const checker = useClaimChecker()
  const { theme, toggleTheme } = useTheme()
  const [page, setPage] = useState<Page>('home')

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [page])

  function goHome() {
    checker.reset()
    setPage('home')
  }

  return (
    <div className="page" data-theme={theme}>
      <NavBar
        current={page}
        theme={theme}
        onToggleTheme={toggleTheme}
        onGoHome={goHome}
        onHowItWorks={() => setPage('how-it-works')}
        onAbout={() => setPage('about')}
      />

      {page === 'how-it-works' && <HowItWorksPage onTryIt={goHome} />}
      {page === 'about' && <AboutPage />}
      {page === 'home' && (
        <SearchScreen
          claim={checker.claim}
          setClaim={checker.setClaim}
          status={checker.status}
          errorMessage={checker.errorMessage}
          checkClaim={checker.checkClaim}
          verdict={checker.verdict}
          activeClaim={checker.activeClaim}
          onHowItWorks={() => setPage('how-it-works')}
        />
      )}
    </div>
  )
}

export default App