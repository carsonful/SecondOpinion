import logoMark from '../assets/so-logo-mark.png'
import { Theme } from '../hooks/useTheme'
import './NavBar.css'

export type Page = 'home' | 'how-it-works' | 'about'

interface NavBarProps {
  current: Page
  theme: Theme
  onToggleTheme: () => void
  onGoHome: () => void
  onHowItWorks: () => void
  onAbout: () => void
}

function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="2" />
      <path
        d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function NavBar({ current, theme, onToggleTheme, onGoHome, onHowItWorks, onAbout }: NavBarProps) {
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <header className="navbar">
      <button type="button" className="navbar__brand" onClick={onGoHome} aria-label="Second Opinion home">
        <img src={logoMark} alt="" className="navbar__logo" />
        <span className="navbar__wordmark">
          <span className="navbar__script">Second</span>
          <span className="navbar__caps">OPINION</span>
        </span>
      </button>
      <nav className="navbar__links">
        <button
          type="button"
          onClick={onHowItWorks}
          aria-current={current === 'how-it-works' ? 'page' : undefined}
        >
          How it works
        </button>
        <button type="button" onClick={onAbout} aria-current={current === 'about' ? 'page' : undefined}>
          About
        </button>
        <button
          type="button"
          className={`navbar__theme navbar__theme--${theme} glass-pill`}
          onClick={onToggleTheme}
          aria-label={`Switch to ${next} mode`}
          title={`Switch to ${next} mode`}
        >
          {/* A two-tone capsule; the icon slides to the half it lights up */}
          <span className="navbar__theme-half" aria-hidden="true" />
          <span key={theme} className="navbar__theme-icon">
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </span>
        </button>
      </nav>
    </header>
  )
}