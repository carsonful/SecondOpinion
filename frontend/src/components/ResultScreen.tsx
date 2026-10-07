import { FormEvent } from 'react'
import { Status } from '../hooks/useClaimChecker.ts'
import { VerdictData } from '../types'
import './ResultScreen.css'

interface ResultScreenProps {
  claim: string
  verdict: VerdictData
  searchValue: string
  onSearchChange: (value: string) => void
  onSearch: (text: string) => void
  status: Status
  errorMessage: string
  onPickRelated: (text: string) => void
}

function verdictKey(verdict: string) {
  const v = verdict.toLowerCase()
  if (v.includes('refut') || v.includes('bust')) return 'refuted'
  if (v.includes('confirm') || v.includes('support')) return 'confirmed'
  return 'unproven'
}

export default function ResultScreen({
  claim,
  verdict,
  searchValue,
  onSearchChange,
  onSearch,
  status,
  errorMessage,
  onPickRelated,
}: ResultScreenProps) {
  const key = verdictKey(verdict.verdict)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onSearch(searchValue)
  }

  return (
    <section className="result">
      <form className="result__search" onSubmit={handleSubmit}>
        <input
          className="result__search-input"
          type="text"
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder='Try "is raw milk better than pasteurized?"'
        />
        <button className="result__search-button" type="submit" disabled={status === 'loading'}>
          {status === 'loading' ? 'Checking…' : 'Check claim'}
        </button>
      </form>

      {status === 'loading' && (
        <div className="result__status glass-panel" role="status">
          <span className="result__spinner" aria-hidden="true" />
          <div>
            <p className="result__status-title">Checking "{searchValue}"</p>
            <p className="result__status-sub">Pulling studies and grading the evidence…</p>
          </div>
        </div>
      )}

      {status === 'error' && (
        <div className="result__status result__status--error glass-panel" role="alert">
          <p className="result__status-title">{errorMessage}</p>
          <p className="result__status-sub">
            Try rephrasing with more specific terms, like the ingredient or condition involved.
          </p>
        </div>
      )}

      {status !== 'loading' && (
        <>
          <p className="result__claim">"{claim}"</p>

          <div className="result__grid">
            <div className={`result__verdict glass-panel result__verdict--${key}`}>
              <span className="result__tag">{verdict.tag}</span>
              <h2 className="result__label">{verdict.verdict}</h2>
              <div className="result__confidence">
                <span>{verdict.confidence} confidence score</span>
                <span
                  className="result__info"
                  title="Calculated from study sample size, type, recency, and whether findings were replicated or retracted."
                >
                  ?
                </span>
              </div>
            </div>

            <div className="result__chat glass-panel">
              <div className="result__chat-avatar">SO</div>
              <div className="result__chat-bubble">{verdict.chatBody}</div>
            </div>
          </div>

          {verdict.relatedClaims && verdict.relatedClaims.length > 0 && (
            <div className="result__related glass-panel">
              <p className="result__related-header">📖 Further reading and related claims</p>
              <div className="result__related-chips">
                {verdict.relatedClaims.map((text) => (
                  <button
                    key={text}
                    type="button"
                    className="result__related-chip"
                    onClick={() => onPickRelated(text)}
                  >
                    {text}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  )
}
