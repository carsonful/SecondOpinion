import { ReactNode } from 'react'

export interface ClaimCandidates {
  status: 'candidates'
  claim: string
  normalized: { query: string }
  total_results: number
  candidates: {
    article: {
      pmid: string
      title: string
      abstract: string | null
      journal: string | null
      year: number | null
      publication_types: string[]
      url: string
    }
    integrity: {
      status: 'retracted' | 'expression_of_concern' | 'corrected' | 'no_notice_found' | 'unchecked'
      notices: { category: string; label: string | null; notice_url: string | null }[]
    }
    metadata: {
      design: string
      design_reason: string
      design_evidence: string | null
      sample_size: number | null
      sample_size_evidence: string | null
      sample_size_reason: string
      animal_only: boolean
    }
    weight: {
      base_weight: number | null
      final_weight: number | null
      version: string
      reason: string
      eligibility_reason: string
    }
  }[]
}

/** One source behind a verdict. Shown as a tab in "Further reading". */
export interface Source {
  title: string
  publisher: string // e.g. "Journal of Food Protection · 2011"
  category: string // evidence category, see docs/evidence-grading.md
  takeaway: string // one sentence: what this source says about the claim
  url: string
  site: string // short label for the link button, e.g. "PubMed"
}

export interface VerdictData {
  verdict: string
  tag: string
  confidence: number
  chatBody: ReactNode
  sources?: Source[]
  relatedClaims?: string[]
}
