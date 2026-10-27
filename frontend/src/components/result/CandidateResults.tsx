import { useId, useState } from 'react'
import { ClaimCandidates } from '../../types'

const DESIGNS: Record<string, string> = {
  randomized_controlled_trial: 'Randomized trial',
  intervention_randomization_unknown: 'Intervention; randomization unknown',
  cohort: 'Cohort', case_control: 'Case-control', cross_sectional: 'Cross-sectional',
  observational_subtype_unknown: 'Observational; subtype unknown',
  case_report_or_series: 'Case report / series', general_review: 'General review',
  commentary: 'Commentary', research_synthesis: 'Research synthesis', unknown: 'Unknown',
}

const MARKS: Record<string, { letter: string; color: string }> = {
  research_synthesis: { letter: 'A', color: 'synthesis' },
  randomized_controlled_trial: { letter: 'B', color: 'randomized' },
  intervention_randomization_unknown: { letter: 'B', color: 'randomized' },
  cohort: { letter: 'C', color: 'observational' },
  case_control: { letter: 'C', color: 'observational' },
  cross_sectional: { letter: 'C', color: 'observational' },
  observational_subtype_unknown: { letter: 'C', color: 'observational' },
  case_report_or_series: { letter: 'D', color: 'descriptive' },
  general_review: { letter: '—', color: 'context' },
  commentary: { letter: '—', color: 'context' },
  unknown: { letter: '—', color: 'unknown' },
}

type Candidate = ClaimCandidates['candidates'][number]

function formatAbstract(abstract: string | null) {
  if (!abstract?.trim()) return <p>No PubMed abstract is available.</p>
  const parts = abstract
    .replace(/\s+(?=(?:BACKGROUND|OBJECTIVE|METHODS|DESIGN|RESULTS|FINDINGS|CONCLUSIONS|CONCLUSION|INTERPRETATION|IMPORTANCE):)/gi, '\n')
    .split(/\n+/).map(part => part.trim()).filter(Boolean)
  return <div className="candidates__abstract-summary">{parts.map((part, index) => {
    const heading = part.match(/^(BACKGROUND|OBJECTIVE|METHODS|DESIGN|RESULTS|FINDINGS|CONCLUSIONS|CONCLUSION|INTERPRETATION|IMPORTANCE):\s*/i)
    return <p key={index}>{heading && <strong>{heading[1].toLowerCase()}: </strong>}{heading ? part.slice(heading[0].length) : part}</p>
  })}</div>
}

export default function CandidateResults({ result, onRefresh }: {
  result: ClaimCandidates; onRefresh: () => void
}) {
  const [sort, setSort] = useState('relevance')
  const sortId = useId()
  const withFullText = result.candidates.filter(candidate => candidate.access.level === 'full_text')
  const abstractOnly = result.candidates.filter(candidate => candidate.access.level !== 'full_text')

  function sorted(rows: Candidate[]) {
    const copy = [...rows]
    if (sort === 'design') copy.sort((a, b) => (DESIGNS[a.metadata.design] ?? 'Unknown').localeCompare(DESIGNS[b.metadata.design] ?? 'Unknown'))
    return copy
  }

  function table(rows: Candidate[], showAbstract: boolean) {
    return <div className="candidates__scroll glass-card" tabIndex={0} role="region" aria-label="Study results; scroll horizontally for more columns">
      <table className="candidates__table">
        <thead><tr><th scope="col">Study</th><th scope="col">Access</th><th scope="col">Study type</th></tr></thead>
        <tbody>{sorted(rows).map(({ article, metadata, access }) => {
          const mark = MARKS[metadata.design] ?? MARKS.unknown
          return <tr key={article.pmid}>
            <td>
              <h3><a href={article.url} target="_blank" rel="noreferrer">{article.title}</a></h3>
              <p>{article.journal || 'Journal unknown'}</p>
              {access.source_url && <p><a href={access.source_url} target="_blank" rel="noreferrer">Open in PMC</a></p>}
              {showAbstract && <div className="candidates__abstract-card"><h4>PubMed abstract</h4>{formatAbstract(article.abstract)}</div>}
              {!showAbstract && <details><summary>Abstract</summary>
                {formatAbstract(article.abstract)}
              </details>}
            </td>
            <td><strong>{access.level === 'full_text' ? 'Full text retrieved' : access.level === 'abstract_only' ? 'Abstract only' : 'Citation only'}</strong>{access.level !== 'full_text' && <p>{access.detail}</p>}</td>
            <td><span className={`study-type study-type--${mark.color}`}>{mark.letter}</span> {DESIGNS[metadata.design] ?? 'Unknown'}</td>
          </tr>
        })}</tbody>
      </table>
    </div>
  }

  return <div className="candidates">
    <h2>Studies for “{result.claim}”</h2>
    <p>{result.candidates.length} studies shown of {result.total_results} PubMed matches.</p>
    <p>{withFullText.length} with retrieved full text; {result.coverage.abstract_only} abstract only; {result.coverage.metadata_only} citation only.</p>
    <p>Study type labels identify research design; access labels say whether PMC full text was retrieved.</p>
    <button className="candidates__refresh" type="button" onClick={onRefresh}>Refresh study access</button>
    {result.cached && <p>Search results came from the cache. Refresh to check access again.</p>}
    {result.candidates.length > 0 && <div className="candidates__sort"><label htmlFor={sortId}>Sort studies</label>
      <select id={sortId} value={sort} onChange={event => setSort(event.target.value)}>
        <option value="relevance">Search relevance</option><option value="design">Study type: A–Z</option>
      </select>
    </div>}
    <section aria-label="Full text retrieved"><h3>Full text retrieved ({withFullText.length})</h3>
      {withFullText.length ? table(withFullText, false) : <p>No full text retrieved for these results.</p>}
    </section>
    <section aria-label="Abstract only or citation only"><h3>Abstract only or citation only ({abstractOnly.length})</h3>
      <p>Full text was not retrieved from the supported PMC source. The abstract remains available below when PubMed provides one.</p>
      {abstractOnly.length ? table(abstractOnly, true) : <p>All listed studies have retrieved full text.</p>}
    </section>
    {result.candidates.length === 0 && <p>No studies matched this search. Try more specific terms.</p>}
  </div>
}
