import { useEffect, useId, useState } from 'react'
import { ClaimCandidates, StudyPopulation } from '../../types'
import { Candidate, Observation, Overview, Reading, SearchResult } from './researchTypes'
import ClipboardBoard from './ClipboardBoard'
import './CandidateResults.css'

type StudyType = { label: string; letter: string; color: string }
const POPULATIONS: Record<StudyPopulation, string> = {
  human: 'Human-indexed · may include mixed populations',
  animal: 'Animal study',
  in_vitro: 'Laboratory / cell study',
  unknown: 'Population not indexed',
}
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


/** Boards on the clipboard: studies grouped by how they were done (not by how good they are). */
const FAMILIES = [
  { id: 'synthesis', title: 'Reviews & meta-analyses', short: 'Reviews', designs: ['research_synthesis'],
    note: 'These papers pull together the results of many studies. Which studies they include still matters, so open the original.',
    tint: { rgb: '11, 25, 87', tab: '#0B1957', tabInk: '#ffffff', tabAlt: '#1B3B6F', tabAltInk: '#ffffff', stamp: '#0B1957' } },
  { id: 'trials', title: 'Trials', short: 'Trials', designs: ['randomized_controlled_trial', 'intervention_randomization_unknown'],
    note: 'In these studies, researchers tested a treatment or intervention and compared what happened.',
    tint: { rgb: '47, 102, 144', tab: '#2F6690', tabInk: '#ffffff', tabAlt: '#A3CEF1', tabAltInk: '#0B1957', stamp: '#2F6690' } },
  { id: 'observational', title: 'Observational studies', short: 'Observational', designs: ['cohort', 'case_control', 'cross_sectional', 'observational_subtype_unknown'],
    note: 'These studies looked at people as they were, without assigning treatments. They can show links, not always causes.',
    tint: { rgb: '214, 180, 130', tab: '#D6B482', tabInk: '#0B1957', tabAlt: '#F6E4C8', tabAltInk: '#0B1957', stamp: '#97691C' } },
  { id: 'other', title: 'Reports, commentary & other', short: 'Reports & other', designs: ['case_report_or_series', 'general_review', 'commentary', 'unknown'],
    note: 'Case reports, commentaries and general overviews add context. They don’t test the claim directly.',
    tint: { rgb: '90, 107, 140', tab: '#5A6B8C', tabInk: '#ffffff', tabAlt: '#C9D3E6', tabAltInk: '#0B1957', stamp: '#5A6B8C' } },
]
/** What the ink stamp says for each study design: a big word and a small line. */
const STAMPS: Record<string, { big: string; sub: string }> = {
  research_synthesis: { big: 'REVIEW', sub: 'RESEARCH SYNTHESIS' },
  randomized_controlled_trial: { big: 'TRIAL', sub: 'RANDOMIZED' },
  intervention_randomization_unknown: { big: 'TRIAL', sub: 'INTERVENTION' },
  cohort: { big: 'COHORT', sub: 'OBSERVATIONAL' },
  case_control: { big: 'CASE-CONTROL', sub: 'OBSERVATIONAL' },
  cross_sectional: { big: 'CROSS-SECTIONAL', sub: 'OBSERVATIONAL' },
  observational_subtype_unknown: { big: 'OBSERVATIONAL', sub: 'TYPE UNKNOWN' },
  case_report_or_series: { big: 'CASE REPORT', sub: 'OR SERIES' },
  general_review: { big: 'OVERVIEW', sub: 'GENERAL REVIEW' },
  commentary: { big: 'COMMENTARY', sub: 'CONTEXT ONLY' },
  unknown: { big: 'UNCLASSIFIED', sub: 'DESIGN UNKNOWN' },
}
function familyOf(design: string) {
  return FAMILIES.find(family => family.designs.includes(design)) ?? FAMILIES[FAMILIES.length - 1]
}

const RELEVANCE_TAB = { direct: 'Direct', related: 'Related', not_addressed: 'Off-topic', unclear: 'Unclear' }
const RELEVANCE = { direct: 'Directly addresses the question', related: 'Related question', not_addressed: 'Does not address the question', unclear: 'Relevance unclear' }

function Citations({ observation, numbers, onSelect, className }: { observation: Observation; numbers: Map<string, number>; onSelect: (pmid: string) => void; className?: string }) {
  return <p className={className}>{observation.text} <span className="research-citations">{[...new Set(observation.pmids)].map(pmid =>
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
        <span>{POPULATIONS[metadata.population ?? 'unknown'] ?? POPULATIONS.unknown}</span>
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
  const [picked, setPicked] = useState<Record<string, string>>({})
  const filterId = useId()
  const studies = result.candidates as Candidate[]
  const excluded = result.excluded_retracted ?? []
  const numbers = new Map(studies.map((study, i) => [study.article.pmid, i + 1]))
  const readings = new Map(overview?.studies.map(reading => [reading.pmid, reading]))
  const shown = studies.filter(study => filter === 'all' || readings.get(study.article.pmid)?.explanation?.relevance === filter)
  const boards = FAMILIES.map(family => ({ ...family, studies: shown.filter(study => familyOf(study.metadata.design).id === family.id) })).filter(board => board.studies.length)
  const mix = FAMILIES.map(family => ({ ...family, count: studies.filter(study => familyOf(study.metadata.design).id === family.id).length })).filter(group => group.count)
  const quick = overview?.synthesis?.observations[0]

  function goToBoard(id: string) {
    setFilter('all')
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    requestAnimationFrame(() => document.getElementById(`board-${id}`)?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }))
  }

  function selectCitation(pmid: string) {
    setFilter('all')
    const study = studies.find(item => item.article.pmid === pmid)
    if (study) setPicked(current => ({ ...current, [familyOf(study.metadata.design).id]: pmid }))
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

  return <div className="vr research-results">
    <div className="vr__top"><span className="search__kicker">YOUR SECOND OPINION</span><span className="search__hand">results are in</span></div>
    <p className="research-claim"><span>“{result.claim}”</span><button type="button" className="research-btn" onClick={onRefresh}>Refresh research <span aria-hidden="true">↻</span></button></p>

    <div className="vr__row">
      <div className="vr__capsule vr__capsule--brief">
        <div className="vr__capsule-top">
          <span className="vr__tag">The research</span>
          <strong className="vr__label">{studies.length} {studies.length === 1 ? 'paper' : 'papers'}</strong>
        </div>
        <div className="vr__seam" />
        <div className="vr__capsule-bottom research-stats">
          <span className="research-stats__title">STUDY TYPES</span>
          <ul className="research-mix">{mix.map(group =>
            <li key={group.id}><button type="button" onClick={() => goToBoard(group.id)}><i style={{ background: group.tint.tab }} aria-hidden="true" /><strong>{group.count}</strong>{group.short}</button></li>)}
          </ul>
          <p className="research-stats__rel"><strong>{overview?.coverage.direct ?? '—'}</strong> directly address your question<br /><strong>{overview?.coverage.related ?? '—'}</strong> address related questions</p>
        </div>
      </div>

      <section className="vr__chat glass-card research-answer" aria-label="Quick read of the research" aria-busy={pending}>
        <div className="vr__chat-body">
          <div className="research-answer__head"><p className="search__kicker">QUICK READ · FROM THE RETRIEVED ABSTRACTS</p><span className="vr__chip">Abstract-based</span></div>
          {pending && <div className="research-loading" role="status"><span className="research-spinner" />Reading the abstracts and comparing them with your claim…<p>The papers are ready below. The overview can take a few minutes.</p></div>}
          {!pending && error && <p role="alert">{error}</p>}
          {quick && <Citations className="research-quick" observation={quick} numbers={numbers} onSelect={selectCitation} />}
          {overview?.synthesis && (overview.synthesis.observations.length > 1 || overview.synthesis.qualifications.length > 0) && <div className="research-observations">
            {overview.synthesis.observations.slice(1).map((observation, i) => <Citations key={i} observation={observation} numbers={numbers} onSelect={selectCitation} />)}
            {overview.synthesis.qualifications.length > 0 && <div className="research-qualifications"><h4>Important qualifications</h4>{overview.synthesis.qualifications.map((observation, i) => <Citations key={i} observation={observation} numbers={numbers} onSelect={selectCitation} />)}</div>}
          </div>}
          {!pending && overview && !overview.synthesis && <p>{overview.status === 'insufficient_information' ? 'The available abstracts do not provide enough usable information for an overview. This does not establish that no evidence exists.' : 'We couldn’t produce a verified overview. Available study explanations and original abstracts remain below.'}</p>}
          {!pending && overview?.status === 'partial' && <p className="research-notice">This overview covers only the successfully analyzed abstracts. Some papers could not be analyzed.</p>}
          {!pending && (error || overview?.status === 'unavailable' || overview?.status === 'partial') && <button type="button" className="research-btn" onClick={expired ? onRefresh : () => setAttempt(value => value + 1)}>{expired ? 'Refresh search' : 'Retry overview'}</button>}
          <p className="research-scope">AI-assisted reading of this search, not a verdict, a systematic review or a study-quality assessment. Citations link to the papers behind each observation.</p>
        </div>
      </section>
    </div>

    <p className="research-coverage-note">Showing {studies.length} papers from {result.total_results.toLocaleString()} PubMed matches{excluded.length ? `; ${excluded.length} retracted ${excluded.length === 1 ? 'paper excluded' : 'papers excluded'}` : ''}. Match counts do not measure evidence strength or relevance.
      {overview && <> {overview.coverage.not_addressed} do not address the question; {overview.coverage.unclear} have unclear relevance; {overview.coverage.no_abstract} lack abstracts; {overview.coverage.withheld} withheld for integrity notices; {overview.coverage.failed} could not be analyzed; {overview.coverage.outside_limit} beyond the 20-paper analysis limit.</>}
      {' '}Listed in PubMed relevance order. Study design describes the research method, not its quality.
    </p>

    <div className="research-filter"><label htmlFor={filterId}>Show </label><select id={filterId} className="research-select" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All retrieved papers</option><option value="direct">Directly relevant</option><option value="related">Related questions</option><option value="not_addressed">Does not address claim</option><option value="unclear">Unclear relevance</option></select></div>
    {boards.map((board, index) => {
      const active = board.studies.find(study => study.article.pmid === picked[board.id]) ?? board.studies[0]
      return <section key={board.id} id={`board-${board.id}`} className={`research-board${index % 2 ? ' research-board--flip' : ''}`} aria-label={board.title}>
        <h3 className="research-board__title"><i style={{ background: board.tint.tab }} aria-hidden="true" />{board.title} <span>{board.studies.length} {board.studies.length === 1 ? 'paper' : 'papers'}</span></h3>
        <ClipboardBoard
          label={board.title}
          caption={`PAPER ${numbers.get(active.article.pmid)} OF ${studies.length}`}
          tint={board.tint}
          stamp={STAMPS[active.metadata.design] ?? STAMPS.unknown}
          onSelect={pmid => setPicked(current => ({ ...current, [board.id]: pmid }))}
          activeId={active.article.pmid}
          asideKicker="STUDY TYPE"
          asideTitle="What this design tells you"
          asideText={board.note}
          tabs={board.studies.map(study => {
            const relevance = readings.get(study.article.pmid)?.explanation?.relevance
            return { id: study.article.pmid, label: `${numbers.get(study.article.pmid)} · ${relevance ? RELEVANCE_TAB[relevance] : 'Paper'}` }
          })}
        >
          <StudyCard key={active.article.pmid} study={active} number={numbers.get(active.article.pmid)!} reading={readings.get(active.article.pmid)} pending={pending} />
        </ClipboardBoard>
      </section>
    })}
    {!shown.length && <p className="research-empty">{studies.length ? 'No papers in this filter. Relevance labels appear after analysis.' : 'No papers were retained for this search. This does not establish that the claim has no research behind it.'}</p>}
    {excluded.length > 0 && <details className="research-excluded"><summary>{excluded.length} retracted {excluded.length === 1 ? 'paper excluded' : 'papers excluded'} from the overview</summary>{excluded.map(study => <div key={study.article.pmid}><h4><a href={study.article.url} target="_blank" rel="noreferrer">{study.article.title}</a></h4><IntegrityNotice study={study} /></div>)}</details>}
    <p className="vr__fine">Second Opinion summarizes research. It isn’t medical advice.</p>
  </div>
}

export default function CandidateResults({ result, onRefresh }: { result: ClaimCandidates; onRefresh: () => void }) {
  const search = result as SearchResult
  return <Results key={search.analysis_id || search.claim} result={search} onRefresh={onRefresh} />
}
