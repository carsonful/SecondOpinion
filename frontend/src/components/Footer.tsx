import { REPO_URL } from '../data/team'
import './Footer.css'

interface FooterProps {
  onHowItWorks: () => void
  onAbout: () => void
}

/** Shown on every page: the medical disclaimer, page links, and project credits. */
export default function Footer({ onHowItWorks, onAbout }: FooterProps) {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <p className="site-footer__disclaimer">
          <strong>Not medical advice.</strong> Second Opinion summarizes published research. It can’t
          diagnose a condition or recommend a treatment. Talk to a doctor or pharmacist about your own health.
        </p>
        <nav className="site-footer__links" aria-label="Footer">
          <button type="button" onClick={onHowItWorks}>How it works</button>
          <button type="button" onClick={onAbout}>About</button>
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            Source code<span className="visually-hidden"> (opens in a new tab)</span> ↗
          </a>
        </nav>
        <p className="site-footer__meta">
          Senior Project · University of Florida · Studies from PubMed, PubMed Central, and Crossref
        </p>
      </div>
    </footer>
  )
}
