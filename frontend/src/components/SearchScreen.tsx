import { FormEvent } from 'react'
import { Status } from '../hooks/useClaimChecker'
import FeatureCards from './FeatureCards'
import './SearchScreen.css'

const EXAMPLE_CLAIMS = [
  'Is raw milk better for you than pasteurized?',
  'Do cold showers boost your immune system?',
  'Does cracking your knuckles cause arthritis?',
]

interface SearchScreenProps {
  claim: string
  setClaim: (value: string) => void
  status: Status
  errorMessage: string
  checkClaim: (text: string) => void
}

export default function SearchScreen({
  claim,
  setClaim,
  status,
  errorMessage,
  checkClaim,
}: SearchScreenProps) {
  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    checkClaim(claim)
  }

  return (
    <>
      <section className="search">
        <p className="search__eyebrow glass-pill">Busting health myths, backed by science</p>
        <h1 className="search__headline">Is that health claim actually true?</h1>
        <p className="search__subhead">
          Paste any health claim and get a science-backed verdict, graded evidence, and sources
          you can trust.
        </p>

        <form className="search__form" onSubmit={handleSubmit}>
          <input
            className="search__input"
            type="text"
            placeholder='Try "is raw milk better than pasteurized?"'
            value={claim}
            onChange={(e) => setClaim(e.target.value)}
          />
          <button className="search__button" type="submit" disabled={status === 'loading'}>
            {status === 'loading' ? 'Checking…' : 'Check claim'}
          </button>
        </form>

        <div className="search__examples">
          {EXAMPLE_CLAIMS.map((example) => (
            <button
              key={example}
              type="button"
              className="search__chip glass-pill"
              onClick={() => {
                setClaim(example)
                checkClaim(example)
              }}
            >
              {example}
            </button>
          ))}
        </div>

        {status === 'loading' && (
          <div className="search__status search__status--loading glass-panel" role="status">
            <span className="search__spinner" aria-hidden="true" />
            <div>
              <p className="search__status-title">Checking "{claim}"</p>
              <p className="search__status-sub">Pulling studies and grading the evidence…</p>
            </div>
          </div>
        )}

        {status === 'error' && (
          <div className="search__status search__status--error glass-panel" role="alert">
            <p className="search__status-title">{errorMessage}</p>
            <p className="search__status-sub">
              Try rephrasing with more specific terms, like the ingredient or condition involved.
            </p>
          </div>
        )}
      </section>

      <FeatureCards />
    </>
  )
}
