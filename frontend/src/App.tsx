import { useState } from 'react'
import './styles/theme.css'
import NavBar from './components/NavBar'
import SearchScreen from './components/SearchScreen'
import ResultScreen from './components/ResultScreen'
import HowItWorksPage from './components/HowItWorksPage'
import AboutPage from './components/AboutPage'
import { useClaimChecker } from './hooks/useClaimChecker'

type Page = 'home' | 'how-it-works' | 'about'

function App() {
  const checker = useClaimChecker()
  const [page, setPage] = useState<Page>('home')

  function goHome() {
    checker.reset()
    setPage('home')
  }

  return (
    <div className="page">
      <NavBar
        onGoHome={goHome}
        onHowItWorks={() => setPage('how-it-works')}
        onAbout={() => setPage('about')}
      />

      {page === 'how-it-works' && <HowItWorksPage />}
      {page === 'about' && <AboutPage />}
      {page === 'home' &&
        (checker.verdict ? (
          <ResultScreen
            claim={checker.activeClaim}
            verdict={checker.verdict}
            searchValue={checker.claim}
            onSearchChange={checker.setClaim}
            onSearch={checker.checkClaim}
            status={checker.status}
            errorMessage={checker.errorMessage}
            onPickRelated={(text) => {
              checker.setClaim(text)
              checker.checkClaim(text)
            }}
          />
        ) : (
          <SearchScreen
            claim={checker.claim}
            setClaim={checker.setClaim}
            status={checker.status}
            errorMessage={checker.errorMessage}
            checkClaim={checker.checkClaim}
          />
        ))}
    </div>
  )
}

export default App
