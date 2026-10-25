import { useId, useState } from 'react'
import { ClaimCandidates } from '../../types'

const LABELS = {
  retracted: 'Retracted — excluded from assessment',
  expression_of_concern: 'Expression of concern — withheld from assessment',
  corrected: 'Correction issued — corrected findings need review',
  no_notice_found: 'No integrity notice found',
  unchecked: 'Integrity not checked',
}

const DESIGNS: Record<string, string> = {
  randomized_controlled_trial: 'Randomized trial',
  intervention_randomization_unknown: 'Intervention; randomization unknown',
  cohort: 'Cohort', case_control: 'Case-control', cross_sectional: 'Cross-sectional',
  observational_subtype_unknown: 'Observational; subtype unknown',
  case_report_or_series: 'Case report / series', general_review: 'General review',
  commentary: 'Commentary', research_synthesis: 'Research synthesis', unknown: 'Unknown',
}

function descendingKnown(a: number | null, b: number | null) {
  if (a === null) return b === null ? 0 : 1
  if (b === null) return -1
  return b - a
}

export default function CandidateResults({ result }: { result: ClaimCandidates }) {
  const [sort, setSort] = useState('relevance')
  const sortId = useId()
  const rows = [...result.candidates]
  if (sort === 'weight') rows.sort((a, b) => descendingKnown(a.weight.base_weight, b.weight.base_weight))
  if (sort === 'year') rows.sort((a, b) => descendingKnown(a.article.year, b.article.year))
  if (sort === 'design') rows.sort((a, b) => {
    if (a.metadata.design === 'unknown') return b.metadata.design === 'unknown' ? 0 : 1
    if (b.metadata.design === 'unknown') return -1
    return (DESIGNS[a.metadata.design] ?? a.metadata.design).localeCompare(DESIGNS[b.metadata.design] ?? b.metadata.design)
  })
  return (
    <div className="candidates">
      <h2>Studies for “{result.claim}”</h2>
      <p>These search results have not been assessed for relevance or findings. A verdict is not available yet.</p>
      <p>{result.candidates.length} shown of {result.total_results} PubMed matches.</p>
      <p>Base weights describe study design. They are provisional project rules, not confidence scores. Final contributions await assessment.</p>
      {result.candidates.length === 0 && <p>No studies matched this search. Try more specific terms.</p>}
      {rows.length > 0 && <>
      <div className="candidates__sort">
        <label htmlFor={sortId}>Sort studies</label>
        <select id={sortId} value={sort} onChange={e => setSort(e.target.value)}>
          <option value="relevance">Search relevance</option>
          <option value="weight">Base weight: highest first</option>
          <option value="year">Year: newest first</option>
          <option value="design">Study type: A–Z</option>
        </select>
      </div>
      <div className="candidates__scroll glass-card" tabIndex={0} role="region" aria-label="Study evidence table; scroll horizontally for more columns">
      <table className="candidates__table">
        <caption>Candidate studies with provisional base design weights. Unknown values are listed last when sorting.</caption>
        <thead><tr>
          <th scope="col">Study and breakdown</th><th scope="col">Year</th>
          <th scope="col">Study type</th><th scope="col">Participants</th>
          <th scope="col">Base weight</th><th scope="col">Integrity</th>
        </tr></thead>
        <tbody>
      {rows.map(({ article, integrity, metadata, weight }) => (
        <tr key={article.pmid}>
          <td>
          <h3><a href={article.url} target="_blank" rel="noreferrer">{article.title}</a></h3>
          <p>{article.journal || 'Journal unknown'}</p>
          {metadata.animal_only && <strong>Animal-only evidence; human applicability not established</strong>}
          <details>
            <summary>View weight breakdown and abstract</summary>
            <p><strong>Base design weight:</strong> {weight.base_weight === null ? 'Unknown' : `${weight.base_weight} / 10`}</p>
            <p>{weight.reason}</p>
            <p><strong>Design:</strong> {metadata.design_reason}</p>
            {metadata.design_evidence && <blockquote>{metadata.design_evidence}</blockquote>}
            <p><strong>Indexed publication types:</strong> {article.publication_types.join(' · ') || 'Unknown'}</p>
            <p><strong>Participant count:</strong> {metadata.sample_size_reason}</p>
            {metadata.sample_size_evidence && <blockquote>{metadata.sample_size_evidence}</blockquote>}
            <p><strong>Final contribution:</strong> {weight.final_weight === null ? 'Pending assessment' : weight.final_weight}</p>
            <p>{weight.eligibility_reason}</p>
            <p><strong>Rule version:</strong> {weight.version}</p>
            <p><strong>Abstract</strong></p>
            <p>{article.abstract || 'No abstract available.'}</p>
          </details>
          </td>
          <td>{article.year ?? 'Unknown'}</td>
          <td>{DESIGNS[metadata.design] ?? 'Unknown'}</td>
          <td>{metadata.sample_size?.toLocaleString() ?? 'Unknown'}</td>
          <td>{weight.base_weight === null ? 'Unknown' : `${weight.base_weight} / 10`}</td>
          <td>
          <strong>{LABELS[integrity.status]}</strong>
          {integrity.status === 'no_notice_found' && <p>This does not establish that the study is trustworthy.</p>}
          {integrity.notices.map((notice, index) => (
            <p key={index}>
              {notice.notice_url
                ? <a href={notice.notice_url} target="_blank" rel="noreferrer">{notice.label || notice.category}</a>
                : notice.label || notice.category}
            </p>
          ))}
          </td>
        </tr>
      ))}
        </tbody>
      </table>
      </div>
      </>}
    </div>
  )
}
