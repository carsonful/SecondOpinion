import { useEffect, useId, useState } from 'react'
import { ClaimCandidates } from '../../types'
import { Candidate, Observation, Overview, Reading, SearchResult } from './researchTypes'
import './CandidateResults.css'

type StudyType = { label: string; letter: string; color: string }
const STUDY_TYPES: Record<string, StudyType> = {
  research_synthesis: { label: 'Research synthesis', letter: 'A', color: 'synthesis' },
  randomized_controlled_trial: { label: 'Randomized trial', letter: 'B', color: 'randomized' },
  intervention_randomization_unknown: { label: 'Intervention; randomization unknown', letter: 'B', color: 'randomized' },
  cohort: { label: 'Cohort', letter: 'C', color: 'observational' },
  case_control: { label: 'Case-control', letter: 'C', color: 'observational' },
  cross_sectional: { label: 'Cross-sectional', letter: 'C', color: 'observational' },
  observational_subtype_unknown: { label: 'Observational; subtype unknown', letter: 'C', color: 'observational' },
  case_report_or_series: { label: 'Case report / series', letter: 'D', color: 'descriptive' },
  general_review: { label: 'General review', letter: '—', color: 'context' },
  commentary: { label: 'Commentary', letter: '—', color: 'context' },
  unknown: { label: 'Unknown', letter: '—', color: 'unknown' },
}


const RELEVANCE = { direct: 'Directly addresses the question', related: 'Related question', not_addressed: 'Does not address the question', unclear: 'Relevance unclear' }

function Citations({ observation, numbers, onSelect }: { observation: Observation; numbers: Map<string, number>; onSelect: (pmid: string) => void }) {
  return <p>{observation.text} <span className="research-citations">{[...new Set(observation.pmids)].map(pmid =>
    <a key={pmid} href={`#study-${pmid}`} aria-label={`Read study ${numbers.get(pmid)}`} onClick={event => { event.preventDefault(); onSelect(pmid) }}>[{numbers.get(pmid)}]</a>,
  )}</span></p>
}

function IntegrityNotice({ study }: { study: Candidate }) {
  const integrity = study.integrity
  if (!integrity) return null
  return <div className={`research-integrity research-integrity--${integrity.status}`}>
    <span>{integrity.label}{integrity.status === 'no_notice_found' ? ' · not a quality assessment' : ''}</span>
    {integrity.notices.map((notice, i) => notice.notice_url &&
      <a key={i} href={notice.notice_url} target="_blank" rel="noreferrer">{notice.label || 'Read notice'} ↗</a>)}
  </div>
}

function StudyCard({ study, number, reading, pending }: { study: Candidate; number: number; reading?: Reading; pending: boolean }) {
  const { article, metadata, access } = study
  const explanation = reading?.explanation
  const type = STUDY_TYPES[metadata.design] ?? STUDY_TYPES.unknown
  return <article className="research-study" id={`study-${article.pmid}`} tabIndex={-1}>
    <div className="research-study__top"><span className="research-study__number">{String(number).padStart(2, '0')}</span>
      <div><div className="research-tags"><span>{type.label}</span><span>{article.year || 'Year unavailable'}</span>
        {explanation && <span className={`research-relevance research-relevance--${explanation.relevance}`}>{RELEVANCE[explanation.relevance]}</span>}
      </div>
      <h3><a href={article.url} target="_blank" rel="noreferrer">{article.title} <span aria-hidden="true">↗</span></a></h3>
      <p className="research-journal">{article.journal || 'Journal not reported'}</p></div>
    </div>
    {explanation ? <>
      <p className="research-study__finding">{explanation.summary.text}</p>
      <div className="research-relationship"><strong>How this relates to your question</strong><p>{explanation.relationship.text}</p></div>
      <details><summary>Explanation and source passages</summary>
        {explanation.gaps.length > 0 && <><h4>What the abstract leaves unclear</h4><ul>{explanation.gaps.map((gap, i) => <li key={i}>{gap}</li>)}</ul></>}
        <h4>Passage supporting the summary</h4><blockquote>{explanation.summary.passage}</blockquote>
        <h4>Passage supporting relevance</h4><blockquote>{explanation.relationship.passage}</blockquote>
      </details>
    </> : <p className="research-muted">{reading?.reason || (!article.abstract?.trim() ? 'No abstract available to analyze.' : pending ? 'Reading this abstract…' : 'No abstract explanation is available yet.')}</p>}
    <details><summary>Read original abstract</summary><p className="research-abstract">{article.abstract || 'PubMed does not provide an abstract for this record.'}</p></details>
    <footer><IntegrityNotice study={study} /><div className="research-links"><a href={article.url} target="_blank" rel="noreferrer">PubMed ↗</a>
      {access.source_url && <a href={access.source_url} target="_blank" rel="noreferrer">PMC full text ↗</a>}
      <span>{access.level === 'full_text' ? 'Full text retrieved; explanation uses abstract' : access.level === 'abstract_only' ? 'Abstract available' : 'Citation only'}</span>
    </div></footer>
  </article>
}

function Results({ result, onRefresh }: { result: SearchResult; onRefresh: () => void }) {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [pending, setPending] = useState(Boolean(result.analysis_id))
  const [error, setError] = useState('')
  const [expired, setExpired] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [filter, setFilter] = useState('all')
  const filterId = useId()
  const studies = result.candidates as Candidate[]
  const excluded = result.excluded_retracted ?? []
  const numbers = new Map(studies.map((study, i) => [study.article.pmid, i + 1]))
  const readings = new Map(overview?.studies.map(reading => [reading.pmid, reading]))
  const shown = studies.filter(study => filter === 'all' || readings.get(study.article.pmid)?.explanation?.relevance === filter)

  function selectCitation(pmid: string) {
    setFilter('all')
    requestAnimationFrame(() => {
      const target = document.getElementById(`study-${pmid}`)
      if (target) {
        window.history.replaceState(null, '', `#study-${pmid}`)
        target.scrollIntoView({ block: 'start' })
        target.focus({ preventScroll: true })
      }
    })
  }

  useEffect(() => {
    if (!result.analysis_id) { setPending(false); setError('Refresh the search to generate a research overview.'); setExpired(true); return }
    const controller = new AbortController()
    setPending(true)
    setError('')
    async function load() {
      try {
        const response = await fetch(`/api/claims/overview/${result.analysis_id}`, { method: 'POST', signal: controller.signal })
        if (response.status === 410) {
          if (!controller.signal.aborted) { setExpired(true); setError('This search session expired. Refresh the search for a new overview.') }
          return
        }
        if (!response.ok) throw new Error('Overview unavailable')
        const data: Overview = await response.json()
        if (!controller.signal.aborted) setOverview(data)
      } catch {
        if (!controller.signal.aborted) setError('We couldn’t finish the overview. Your studies are still available below.')
      } finally {
        if (!controller.signal.aborted) setPending(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [result.analysis_id, attempt])

  return <div className="research-results">
    <header className="research-header"><div><p className="research-eyebrow">YOUR RESEARCH BRIEF</p><h2>{result.claim}</h2>
      <p>A closer look at the research behind your question.</p></div><button type="button" onClick={onRefresh}>Refresh research <span aria-hidden="true">↻</span></button></header>
    <section className="research-overview" aria-labelledby="overview-title" aria-busy={pending}>
      <div className="research-overview__heading"><span className="research-orbit" aria-hidden="true">✦</span><div><p className="research-eyebrow">FROM THE RETRIEVED ABSTRACTS</p><h3 id="overview-title">What the research suggests</h3></div><span className="research-basis">Abstract-based</span></div>
      {pending && <div className="research-loading" role="status"><span className="research-spinner" />Reading the abstracts and comparing them with your claim…<p>The papers are ready below. The overview can take a few minutes.</p></div>}
      {!pending && error && <p role="alert">{error}</p>}
      {overview?.synthesis && <div className="research-observations">{overview.synthesis.observations.map((observation, i) => <Citations key={i} observation={observation} numbers={numbers} onSelect={selectCitation} />)}
        {overview.synthesis.qualifications.length > 0 && <div className="research-qualifications"><h4>Important qualifications</h4>{overview.synthesis.qualifications.map((observation, i) => <Citations key={i} observation={observation} numbers={numbers} onSelect={selectCitation} />)}</div>}
      </div>}
      {!pending && overview && !overview.synthesis && <p>{overview.status === 'insufficient_information' ? 'The available abstracts do not provide enough usable information for an overview. This does not establish that no evidence exists.' : 'We couldn’t produce a verified overview. Available study explanations and original abstracts remain below.'}</p>}
      {!pending && overview?.status === 'partial' && <p className="research-notice">This overview covers only the successfully analyzed abstracts. Some papers could not be analyzed.</p>}
      {!pending && (error || overview?.status === 'unavailable' || overview?.status === 'partial') && <button type="button" onClick={expired ? onRefresh : () => setAttempt(value => value + 1)}>{expired ? 'Refresh search' : 'Retry overview'}</button>}
      <p className="research-scope">AI-assisted reading of this search, not a systematic review or a study-quality assessment. Citations link to the papers behind each observation.</p>
    </section>
    <section className="research-coverage" aria-label="Research coverage">
      <div><strong>{studies.length}</strong><span>papers retrieved</span></div><div><strong>{overview?.coverage.analyzed ?? '—'}</strong><span>abstracts analyzed</span></div>
      <div><strong>{overview?.coverage.direct ?? '—'}</strong><span>directly address the question</span></div><div><strong>{overview?.coverage.related ?? '—'}</strong><span>address related questions</span></div>
    </section>
    <p className="research-coverage-note">Showing {studies.length} papers from {result.total_results.toLocaleString()} PubMed matches{excluded.length ? `; ${excluded.length} retracted ${excluded.length === 1 ? 'paper excluded' : 'papers excluded'}` : ''}. Match counts do not measure evidence strength or relevance.
      {overview && <> {overview.coverage.not_addressed} do not address the question; {overview.coverage.unclear} have unclear relevance; {overview.coverage.no_abstract} lack abstracts; {overview.coverage.withheld} withheld for integrity notices; {overview.coverage.failed} could not be analyzed; {overview.coverage.outside_limit} beyond the 20-paper analysis limit.</>}
    </p>
    <div className="research-list-heading"><div><p className="research-eyebrow">EXPLORE THE SOURCES</p><h3>The studies behind this search</h3></div>
      <div><label htmlFor={filterId}>Show </label><select id={filterId} value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All retrieved papers</option><option value="direct">Directly relevant</option><option value="related">Related questions</option><option value="not_addressed">Does not address claim</option><option value="unclear">Unclear relevance</option></select></div></div>
    <p className="research-muted">Listed in PubMed relevance order. Study design describes the research method, not its quality.</p>
    <div className="research-study-list">{shown.map(study => <StudyCard key={study.article.pmid} study={study} number={numbers.get(study.article.pmid)!} reading={readings.get(study.article.pmid)} pending={pending} />)}</div>
    {!shown.length && <p className="research-empty">{studies.length ? 'No papers in this filter. Relevance labels appear after analysis.' : 'No papers were retained for this search. This does not establish that the claim has no research behind it.'}</p>}
    {excluded.length > 0 && <details className="research-excluded"><summary>{excluded.length} retracted {excluded.length === 1 ? 'paper excluded' : 'papers excluded'} from the overview</summary>{excluded.map(study => <div key={study.article.pmid}><h4><a href={study.article.url} target="_blank" rel="noreferrer">{study.article.title}</a></h4><IntegrityNotice study={study} /></div>)}</details>}
  </div>
}

export default function CandidateResults({ result, onRefresh }: { result: ClaimCandidates; onRefresh: () => void }) {
  const search = result as SearchResult
  return <Results key={search.analysis_id || search.claim} result={search} onRefresh={onRefresh} />
}
