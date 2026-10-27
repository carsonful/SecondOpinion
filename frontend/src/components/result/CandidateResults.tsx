import { useId, useState } from 'react'
import { ClaimCandidates, FullTextAccess } from '../../types'

type Candidate = ClaimCandidates['candidates'][number]
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

const ACCESS_LABELS: Record<FullTextAccess['level'], string> = {
  full_text: 'Full text retrieved',
  abstract_only: 'Abstract only',
  metadata_only: 'Citation only',
}

const ABSTRACT_HEADINGS = 'BACKGROUND|OBJECTIVE|METHODS|DESIGN|RESULTS|FINDINGS|CONCLUSIONS|CONCLUSION|INTERPRETATION|IMPORTANCE'
const ABSTRACT_SECTION_BREAK = new RegExp(`\\s+(?=(?:${ABSTRACT_HEADINGS}):)`, 'gi')
const ABSTRACT_HEADING = new RegExp(`^(${ABSTRACT_HEADINGS}):\\s*`, 'i')

function studyType(design: string): StudyType {
  return STUDY_TYPES[design] ?? STUDY_TYPES.unknown
}

function AbstractSummary({ abstract }: { abstract: string | null }) {
  if (!abstract?.trim()) return <p>No PubMed abstract is available.</p>

  const paragraphs = abstract
    .replace(ABSTRACT_SECTION_BREAK, '\n')
    .split(/\n+/)
    .map(part => part.trim())
    .filter(Boolean)

  return (
    <div className="candidates__abstract-summary">
      {paragraphs.map((paragraph, index) => {
        const heading = paragraph.match(ABSTRACT_HEADING)
        const body = heading ? paragraph.slice(heading[0].length) : paragraph
        return (
          <p key={index}>
            {heading && <strong>{heading[1].toLowerCase()}: </strong>}
            {body}
          </p>
        )
      })}
    </div>
  )
}

function StudyTable({ rows, showAbstract }: { rows: Candidate[]; showAbstract: boolean }) {
  return (
    <div className="candidates__scroll glass-card" tabIndex={0} role="region" aria-label="Study results; scroll horizontally for more columns">
      <table className="candidates__table">
        <thead>
          <tr>
            <th scope="col">Study</th>
            <th scope="col">Access</th>
            <th scope="col">Study type</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ article, metadata, access }) => {
            const type = studyType(metadata.design)
            return (
              <tr key={article.pmid}>
                <td>
                  <h3><a href={article.url} target="_blank" rel="noreferrer">{article.title}</a></h3>
                  <p>{article.journal || 'Journal unknown'}</p>
                  {access.source_url && (
                    <p><a href={access.source_url} target="_blank" rel="noreferrer">Open in PMC</a></p>
                  )}
                  {showAbstract ? (
                    <div className="candidates__abstract-card">
                      <h4>PubMed abstract</h4>
                      <AbstractSummary abstract={article.abstract} />
                    </div>
                  ) : (
                    <details>
                      <summary>Abstract</summary>
                      <AbstractSummary abstract={article.abstract} />
                    </details>
                  )}
                </td>
                <td>
                  <strong>{ACCESS_LABELS[access.level]}</strong>
                  {access.level !== 'full_text' && <p>{access.detail}</p>}
                </td>
                <td>
                  <span className={`study-type study-type--${type.color}`}>{type.letter}</span> {type.label}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

interface CandidateResultsProps {
  result: ClaimCandidates
  onRefresh: () => void
}

export default function CandidateResults({ result, onRefresh }: CandidateResultsProps) {
  const [sort, setSort] = useState('relevance')
  const sortId = useId()
  const studies = [...result.candidates]
  if (sort === 'design') {
    studies.sort((a, b) => studyType(a.metadata.design).label.localeCompare(studyType(b.metadata.design).label))
  }
  const withFullText = studies.filter(candidate => candidate.access.level === 'full_text')
  const withoutFullText = studies.filter(candidate => candidate.access.level !== 'full_text')

  return (
    <div className="candidates">
      <h2>Studies for “{result.claim}”</h2>
      <p>{studies.length} studies shown of {result.total_results} PubMed matches.</p>
      <p>{withFullText.length} with retrieved full text; {result.coverage.abstract_only} abstract only; {result.coverage.metadata_only} citation only.</p>
      <p>Study type labels identify research design; access labels say whether PMC full text was retrieved.</p>
      <button className="candidates__refresh" type="button" onClick={onRefresh}>Refresh study access</button>
      {result.cached && <p>Search results came from the cache. Refresh to check access again.</p>}
      {studies.length > 0 && (
        <div className="candidates__sort">
          <label htmlFor={sortId}>Sort studies</label>
          <select id={sortId} value={sort} onChange={event => setSort(event.target.value)}>
            <option value="relevance">Search relevance</option>
            <option value="design">Study type: A–Z</option>
          </select>
        </div>
      )}
      <section aria-label="Full text retrieved">
        <h3>Full text retrieved ({withFullText.length})</h3>
        {withFullText.length > 0 ? (
          <StudyTable rows={withFullText} showAbstract={false} />
        ) : <p>No full text retrieved for these results.</p>}
      </section>
      <section aria-label="Abstract only or citation only">
        <h3>Abstract only or citation only ({withoutFullText.length})</h3>
        <p>Full text was not retrieved from the supported PMC source. The abstract remains available below when PubMed provides one.</p>
        {withoutFullText.length > 0 ? (
          <StudyTable rows={withoutFullText} showAbstract />
        ) : <p>All listed studies have retrieved full text.</p>}
      </section>
      {studies.length === 0 && <p>No studies matched this search. Try more specific terms.</p>}
    </div>
  )
}
