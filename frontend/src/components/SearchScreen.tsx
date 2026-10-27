import { FormEvent, useEffect, useRef } from 'react'
import { Status } from '../hooks/useClaimChecker'
import { ClaimCandidates, VerdictData } from '../types'
import { EXAMPLE_CLAIMS } from '../data/exampleClaims'
import VerdictResult from './result/VerdictResult'
import CandidateResults from './result/CandidateResults'
import './SearchScreen.css'

const CAP_COLORS = [
  'linear-gradient(135deg,#3d8ed6,#2a6cb8)',
  'linear-gradient(135deg,#F6E4C8,#D6B482)',
  'linear-gradient(135deg,#1B3B6F,#0B1957)',
]

const CHECKS = [
  { title: 'Claim normalization', text: 'Understands what you’re actually asking', cap: '#2a6cb8' },
  { title: 'Study types', text: 'Learn what each design can tell you', cap: '#D6B482' },
  { title: 'PMC full text', text: 'See whether the full text is available', cap: '#0B1957' },
]

interface SearchScreenProps {
  claim: string
  setClaim: (value: string) => void
  status: Status
  errorMessage: string
  checkClaim: (text: string, refresh?: boolean) => void
  verdict: VerdictData | null
  candidates: ClaimCandidates | null
  activeClaim: string
  onHowItWorks?: () => void
}

/**
 * Search and result on one page. The top follows the theme (ink & cream in
 * dark mode); the bottom, where the result appears, is always light.
 */
export default function SearchScreen({
  claim,
  setClaim,
  status,
  errorMessage,
  checkClaim,
  verdict,
  candidates,
  activeClaim,
  onHowItWorks,
}: SearchScreenProps) {
  const resultRef = useRef<HTMLDivElement>(null)
  const showResult = status === 'success' && Boolean(verdict || candidates)

  // Bring the result into view when it arrives
  useEffect(() => {
    if (showResult) resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [showResult, activeClaim])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    checkClaim(claim)
  }

  function pick(text: string) {
    setClaim(text)
    checkClaim(text)
  }

  const examples = EXAMPLE_CLAIMS.filter(
    ({ claim: text }) => !(showResult && text.toLowerCase() === activeClaim.toLowerCase()),
  )

  return (
    <div className="search-page">
      <section className="search__top">
        <div className="search">
          <p className="search__eyebrow glass-pill">Busting health myths, backed by science</p>
          <h1 className="search__headline">
            Is that health claim
            <br />
            actually true?
          </h1>
          <p className="search__subhead">
            Search a health claim to explore related studies, learn their designs, and open the available sources.
          </p>

          <form className="search__capsule" onSubmit={handleSubmit} role="search">
            <label className="search__capsule-input glass-card">
              <span className="visually-hidden">Health claim</span>
              <input
                type="text"
                placeholder='Try "is raw milk better than pasteurized?"'
                value={claim}
                maxLength={2000}
                onChange={(e) => setClaim(e.target.value)}
              />
            </label>
            <span className="search__capsule-seam" aria-hidden="true" />
            <button className="search__capsule-btn" type="submit" disabled={status === 'loading'}>
              {status === 'loading' ? 'Checking…' : 'Check claim'}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </form>

          <div className="search__examples">
            <span className="search__hand search__hand--top">{showResult ? 'try another:' : 'or try one:'}</span>
            {examples.map(({ slug, claim: text }) => (
              <button
                key={slug}
                type="button"
                className="search__chip search__chip--top"
                onClick={() => pick(text)}
              >
                <span>{text}</span>
                <span style={{ background: CAP_COLORS[EXAMPLE_CLAIMS.findIndex((item) => item.slug === slug)] }} />
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="search__bottom theme-light" ref={resultRef} aria-live="polite">
        <div className="search__bottom-inner">
          {status === 'loading' && (
            <div className="search__status glass-card" role="status">
              <span className="search__spinner" aria-hidden="true" />
              <div>
                <p className="search__status-title">Checking “{claim}”</p>
                <p className="search__status-sub">Preparing your result…</p>
              </div>
            </div>
          )}

          {status === 'error' && (
            <div className="search__status search__status--error glass-card" role="alert">
              <p className="search__status-title">{errorMessage}</p>
              <p className="search__status-sub">
                Try rephrasing with more specific terms, like the ingredient or condition involved.
              </p>
              <button type="button" onClick={() => checkClaim(claim)}>Try again</button>
            </div>
          )}

          {showResult && verdict && (
            <VerdictResult key={activeClaim} verdict={verdict} onPickRelated={pick} onHowItWorks={onHowItWorks} />
          )}
          {showResult && candidates && <CandidateResults result={candidates} onRefresh={() => checkClaim(activeClaim, true)} />}

          {status === 'idle' && (
            <div className="checks">
              <h2>Three checks, every claim</h2>
              <div className="checks__strip">
                <span className="checks__title">THREE CHECKS · EVERY CLAIM</span>
                <div className="checks__row">
                  {CHECKS.map((c) => (
                    <div key={c.title} className="checks__cell">
                      <span className="checks__pocket" aria-hidden="true">
                        <span
                          className="checks__pill"
                          style={{ background: `linear-gradient(180deg,#ffffff 50%,${c.cap} 50%)` }}
                        />
                      </span>
                      <span className="checks__copy">
                        <strong>{c.title}</strong>
                        <span>{c.text}</span>
                      </span>
                    </div>
                  ))}
                </div>
                {onHowItWorks && (
                  <button type="button" className="checks__link" onClick={onHowItWorks}>
                    See how it works →
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
