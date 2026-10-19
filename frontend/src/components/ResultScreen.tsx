import { FormEvent, useEffect, useRef, useState } from 'react'
import { ClaimResult, StudyAssessment } from '../types'
import './ResultScreen.css'

interface ResultScreenProps {
  result: ClaimResult
  searchValue: string
  onSearchChange: (value: string) => void
  onSearch: (text: string) => void
}

function Assessment({ initial, claim }: { initial: StudyAssessment; claim: string }) {
  const [assessment, setAssessment] = useState(initial)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])

  async function assess() {
    controller.current?.abort()
    const request = new AbortController()
    controller.current = request
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`/api/claims/articles/${initial.pmid}/assess`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim }), signal: request.signal,
      })
      if (!response.ok) throw new Error(response.status === 502
        ? 'The generated assessment could not be verified against the abstract. Please retry.'
        : 'Assessment service unavailable. Please try again shortly.')
      const data: StudyAssessment = await response.json()
      if (!request.signal.aborted) setAssessment(data)
    } catch (failure) {
      if (!request.signal.aborted) setError(failure instanceof Error && !(failure instanceof TypeError)
        ? failure.message : 'Cannot reach the assessment service. Please try again.')
    } finally {
      if (!request.signal.aborted) setLoading(false)
    }
  }

  return (
    <div className="result__assessment">
      <p><strong>{assessment.category}</strong></p>
      {assessment.assessment_status === 'completed' ? <>
        <p><strong>Finding: {assessment.finding.split('_').join(' ')}</strong> · Relevance: {assessment.relevance.split('_').join(' ')}</p>
        <p>{assessment.summary}</p>
        {assessment.measurement_warnings.map(warning => <p role="status" key={warning}>{warning}</p>)}
        <details><summary>Reported sample sizes and effects</summary>
          <h3>Sample sizes</h3>
          {assessment.sample_sizes.length === 0 && <p>No verified value available from the abstract.</p>}
          {assessment.sample_sizes.map((item, index) => <div key={index}><strong>{item.reported}</strong><blockquote>{item.passage}</blockquote></div>)}
          <h3>Effect estimates</h3>
          {assessment.effect_estimates.length === 0 && <p>No verified value available from the abstract.</p>}
          {assessment.effect_estimates.map((item, index) => <div key={index}><strong>{item.reported}</strong><blockquote>{item.passage}</blockquote></div>)}
          <p>Reported values are shown with their abstract context; no missing values are calculated.</p>
        </details>
        <details><summary>Supporting abstract passages</summary>
          {assessment.supporting_passages.map((quote, index) => <blockquote key={index}>{quote}</blockquote>)}
        </details>
        <p className="result__metadata">AI interpretation of the abstract; this is not an overall verdict.</p>
      </> : <p>Findings and relevance: not yet assessed.</p>}
      {assessment.assessment_status === 'pending' && assessment.eligibility !== 'excluded' &&
        <button type="button" className="result__related-chip" disabled={loading} onClick={assess}>
          {loading ? 'Assessing abstract…' : 'Assess abstract'}
        </button>}
      {loading && <p role="status">Reading this study’s abstract…</p>}
      {error && <p role="alert">{error}</p>}
      <p>{assessment.eligibility_reason}</p>
      {assessment.flags.length > 0 && <ul>{assessment.flags.map(flag => <li key={flag}>{flag}</li>)}</ul>}
      <details>
        <summary>Preliminary design weight</summary>
        <p>{assessment.base_weight === null ? 'Unknown' : `${assessment.base_weight} / 10`} · {assessment.weight_version}</p>
        <p>This is a provisional design default for human intervention effects, not a quality rating or confidence score. It does not establish whether this paper answers your claim.</p>
      </details>
    </div>
  )
}

export default function ResultScreen({ result, searchValue, onSearchChange, onSearch }: ResultScreenProps) {
  const assessments = new Map(result.assessments.map(item => [item.pmid, item]))

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onSearch(searchValue)
  }

  return (
    <section className="result">
      <form className="result__search" onSubmit={handleSubmit}>
        <input className="result__search-input" type="text" aria-label="Health claim"
          maxLength={2000} required value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)} placeholder="Enter another health claim" />
        <button className="result__search-button" type="submit">Find studies</button>
      </form>
      <h1 className="result__claim">“{result.claim}”</h1>
      <div className="result__summary glass-panel" role="status">
        <h2>Explore study findings</h2>
        <p>Study categories are based on PubMed metadata. Choose “Assess abstract” on a study to explore its relevance and findings. An overall verdict is not available yet.</p>
        <p>Showing {result.evidence.articles.length} of {result.evidence.total_results} PubMed matches.</p>
        {result.search_scope === 'intervention_only' && <p>
          No matches were found for the full claim. These broader results cover the intervention or exposure and may not address your health outcome or population.
        </p>}
        <details><summary>Search details</summary>
          <p>Original query: {result.normalized.query}</p>
          <p>Query used: {result.evidence.query}</p>
        </details>
      </div>
      {result.evidence.articles.length === 0 && (
        <div className="result__summary glass-panel">
          <h2>No studies found</h2>
          <p>Try specifying the ingredient, treatment, or health outcome. No matches does not establish whether a claim is true or false.</p>
        </div>
      )}
      <div className="result__studies">
        {result.evidence.articles.map((article) => (
          <article className="result__study glass-panel" key={article.pmid}>
            <h2><a href={`https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`} target="_blank" rel="noopener noreferrer">{article.title}</a></h2>
            <p className="result__metadata">{article.journal ?? 'Journal unavailable'} · {article.year ?? 'Year unavailable'} · PMID {article.pmid}</p>
            {article.retracted && <p className="result__retracted">Retracted publication — flagged by PubMed.</p>}
            {article.integrity_links.length > 0 && <div className="result__integrity">
              <strong>Linked integrity records</strong>
              <ul>{article.integrity_links.map((link, index) => <li key={index}>
                {{ RetractionIn: 'Retraction notice', RetractionOf: 'Article retracted by this notice',
                  ErratumIn: 'Correction notice', ErratumFor: 'Article corrected by this notice',
                  ExpressionOfConcernIn: 'Expression of concern', ExpressionOfConcernFor: 'Article addressed by this concern' }[link.relation] ?? link.relation}
                {link.pmid && <> — <a href={`https://pubmed.ncbi.nlm.nih.gov/${link.pmid}/`} target="_blank" rel="noopener noreferrer">PMID {link.pmid}</a></>}
                {link.citation && <p>{link.citation}</p>}{link.note && <p>{link.note}</p>}
              </li>)}</ul>
              <p>Linked corrections and concerns require review; their impact has not been resolved.</p>
            </div>}
            <p className="result__metadata">{article.publication_types.join(' · ') || 'Publication type unavailable'}</p>
            {assessments.has(article.pmid) && <Assessment key={`${result.claim}:${article.pmid}`} initial={assessments.get(article.pmid)!} claim={result.claim} />}
            {article.abstract ? <details><summary>Read abstract</summary><p className="result__abstract">{article.abstract}</p></details> : <p>Abstract unavailable — limited information.</p>}
          </article>
        ))}
      </div>
    </section>
  )
}
