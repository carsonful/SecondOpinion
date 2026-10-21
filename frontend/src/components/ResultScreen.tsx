import { useEffect, useRef, useState } from 'react'
import { ClaimResult, StudyAssessment } from '../types'
import './ResultScreen.css'

interface ResultScreenProps {
  result: ClaimResult
}

function Assessment({ initial, claim, hasAbstract }: { initial: StudyAssessment; claim: string; hasAbstract: boolean }) {
  const [assessment, setAssessment] = useState(initial)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [mode, setMode] = useState<'abstract' | 'full_text' | 'pdf'>('abstract')
  const [pdf, setPdf] = useState<File | null>(null)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])

  async function assess(nextMode: 'abstract' | 'full_text' | 'pdf' = 'abstract') {
    const upload = nextMode === 'pdf'
    if (upload && !pdf) return
    controller.current?.abort()
    const request = new AbortController()
    controller.current = request
    setLoading(true)
    setMode(nextMode)
    setError('')
    setNotice('')
    try {
      const form = new FormData()
      form.append('claim', claim)
      if (upload && pdf) form.append('file', pdf)
      const response = await fetch(`/api/claims/articles/${initial.pmid}/${upload ? 'assess-pdf' : nextMode === 'abstract' ? 'assess' : 'assess-full-text'}`, {
        method: 'POST',
        headers: upload ? undefined : { 'Content-Type': 'application/json' },
        body: upload ? form : JSON.stringify({ claim }), signal: request.signal,
      })
      if (!response.ok) {
        const failure = await response.json().catch(() => ({}))
        throw new Error(typeof failure.detail === 'string' ? failure.detail
          : 'Study assessment failed. Check your file or try again shortly.')
      }
      const data: StudyAssessment = await response.json()
      if (!request.signal.aborted) {
        if (data.assessment_status !== 'completed' && assessment.assessment_status === 'completed') {
          setNotice(data.coverage_note ?? 'The additional review was unavailable. Your previous assessment is shown below.')
        } else {
          setAssessment(data)
        }
      }
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
      {notice && <p role="status">{notice}</p>}
      {assessment.coverage_note && <p role="status">{assessment.coverage_note}</p>}
      {assessment.assessment_basis && <p>Assessment source: {assessment.assessment_basis === 'full_text' ? ({ pmc: 'PMC article text', publisher_html: 'Publisher/repository HTML', downloaded_pdf: 'Downloaded PDF', uploaded_pdf: 'Uploaded PDF' }[assessment.source_kind ?? 'pmc']) : 'PubMed abstract only'}.
        {assessment.source_url && <> <a href={assessment.source_url} target="_blank" rel="noopener noreferrer">Read source</a></>}
      </p>}
      {assessment.assessment_status === 'completed' ? <>
        <p><strong>Finding: {assessment.finding.split('_').join(' ')}</strong> · Relevance: {assessment.relevance.split('_').join(' ')}</p>
        <h3>Reported study information and results</h3>
        <p>{assessment.summary}</p>
        {assessment.measurement_warnings.map(warning => <p role="status" key={warning}>{warning}</p>)}
        <details><summary>Reported sample sizes and effects</summary>
          <h3>Sample sizes</h3>
          {assessment.sample_sizes.length === 0 && <p>{assessment.assessment_basis === 'abstract' ? 'Not reported or not verified in the abstract.' : 'Not reported or not verified in the assessed text.'}</p>}
          {assessment.sample_sizes.map((item, index) => <div key={index}><strong>{item.reported}</strong><blockquote>{item.passage}</blockquote></div>)}
          <h3>Effect estimates</h3>
          {assessment.effect_estimates.length === 0 && <p>{assessment.assessment_basis === 'abstract' ? 'Not reported or not verified in the abstract.' : 'Not reported or not verified in the assessed text.'}</p>}
          {assessment.effect_estimates.map((item, index) => <div key={index}><strong>{item.reported}</strong><blockquote>{item.passage}</blockquote></div>)}
          <p>Reported values are shown with their source context; no missing values are calculated.</p>
        </details>
        <details><summary>Supporting study passages</summary>
          {assessment.supporting_passages.map((quote, index) => <blockquote key={index}>{quote}</blockquote>)}
        </details>
        <p className="result__metadata">AI interpretation of the {assessment.assessment_basis === 'abstract' ? 'abstract only' : 'available full text'}; this is not an overall verdict.</p>
      </> : <p>Findings and relevance: not yet assessed.</p>}
      {initial.eligibility !== 'excluded' && !initial.flags.some(flag => flag.includes('Integrity notice')) && <>
        {assessment.assessment_status !== 'completed' && <>
          <button type="button" className="result__related-chip" disabled={loading || !hasAbstract} onClick={() => assess()}>
            {loading && mode === 'abstract' ? 'Assessing abstract…' : 'Assess abstract'}
          </button>
          {!hasAbstract && <p>No abstract is available for this study. You can try full-text review below.</p>}
        </>}
        {!(assessment.assessment_status === 'completed' && assessment.assessment_basis === 'full_text') && <details>
          <summary>Optional full-text review</summary>
          <p>Review an available full article or upload a PDF. This makes a separate assessment request.</p>
          <button type="button" className="result__related-chip" disabled={loading} onClick={() => assess('full_text')}>Find full text and assess</button>
        <div className="result__upload">
          <label>Use a PDF from your library or the publisher
            <input type="file" accept="application/pdf,.pdf" disabled={loading} onChange={(event) => {
              const selected = event.target.files?.[0] ?? null
              if (selected && selected.size > 10 * 1024 * 1024) {
                setError('Choose a PDF of at most 10 MB.')
                setPdf(null)
              } else {
                setError('')
                setPdf(selected)
              }
            }} />
          </label>
          <p className="result__metadata">Text-based PDF, up to 10 MB and 100 pages. The extracted text is sent for AI assessment when you click below; the file is not retained by the app.</p>
          <button type="button" className="result__related-chip" disabled={loading || !pdf} onClick={() => assess('pdf')}>Upload PDF and assess</button>
        </div>
        </details>}
      </>}
      {loading && <p role="status">{mode === 'abstract' ? 'Reading the abstract for study information and reported results…' : 'Retrieving and reading the available full study text…'}</p>}
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

export default function ResultScreen({ result }: ResultScreenProps) {
  const assessments = new Map(result.assessments.map(item => [item.pmid, item]))

  return (
    <section className="result">
      <h1 className="result__claim">“{result.claim}”</h1>
      <div className="result__summary glass-panel" role="status">
        <h2>Explore study findings</h2>
        <p>Study categories are based on PubMed metadata. Choose “Assess abstract” to review reported study information, results and relevance. Full-text review is optional. An overall verdict is not available yet.</p>
        <p>Showing {result.evidence.articles.length} of {result.evidence.total_results} PubMed matches, ordered by PubMed relevance (up to 5 studies).</p>
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
            {article.doi && <p><a href={`https://doi.org/${encodeURIComponent(article.doi)}`} target="_blank" rel="noopener noreferrer">Open publisher page / get PDF</a></p>}
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
            {assessments.has(article.pmid) && <Assessment key={`${result.claim}:${article.pmid}`} initial={assessments.get(article.pmid)!} claim={result.claim} hasAbstract={Boolean(article.abstract?.trim())} />}
            {article.abstract ? <details><summary>Read abstract</summary><p className="result__abstract">{article.abstract}</p></details> : <p>Abstract unavailable — limited information.</p>}
          </article>
        ))}
      </div>
    </section>
  )
}
