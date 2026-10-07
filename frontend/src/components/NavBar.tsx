import logoMark from '../assets/so-logo-mark.png'
import './NavBar.css'

interface NavBarProps {
  onGoHome: () => void
  onHowItWorks: () => void
  onAbout: () => void
}

export default function NavBar({ onGoHome, onHowItWorks, onAbout }: NavBarProps) {
  return (
    <header className="navbar">
      <button type="button" className="navbar__brand" onClick={onGoHome}>
        <img src={logoMark} alt="" className="navbar__logo" />
        <span className="navbar__wordmark">
          <span className="navbar__script">Second</span>
          <span className="navbar__caps">OPINION</span>
        </span>
      </button>
      <nav className="navbar__links">
        <button type="button" onClick={onHowItWorks}>
          How it works
        </button>
        <button type="button" onClick={onAbout}>
          About
        </button>
      </nav>
    </header>
  )
}
