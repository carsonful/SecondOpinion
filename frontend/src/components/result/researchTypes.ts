import { ClaimCandidates } from '../../types'
export type Integrity = { status: string; label: string; notices: { notice_url: string | null; label: string | null }[] }
export type Candidate = ClaimCandidates['candidates'][number] & { integrity?: Integrity }
export type SearchResult = ClaimCandidates & { analysis_id?: string; excluded_retracted?: Candidate[] }
export type Explanation = {
  summary: { text: string; passage: string }
  relevance: 'direct' | 'related' | 'not_addressed' | 'unclear'
  relationship: { text: string; passage: string }
  gaps: string[]
}
export type Reading = { pmid: string; status: string; reason: string | null; explanation: Explanation | null }
export type Observation = { text: string; pmids: string[] }
export type Overview = {
  status: 'complete' | 'partial' | 'unavailable' | 'insufficient_information'
  coverage: { retrieved: number; analyzed: number; direct: number; related: number; not_addressed: number; unclear: number; no_abstract: number; withheld: number; failed: number; outside_limit: number; excluded_retracted: number }
  studies: Reading[]
  synthesis: { observations: Observation[]; qualifications: Observation[] } | null
  cached: boolean
}
