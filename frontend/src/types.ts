import { ReactNode } from 'react'

export type StudyPopulation = 'human' | 'animal' | 'in_vitro' | 'unknown'

export interface FullTextAccess {
  level: 'full_text' | 'abstract_only' | 'metadata_only'
  reason: string
  detail: string
  pmc_id: string | null
  source_url: string | null
  license: string | null
  sections: string[]
}

export interface ClaimCandidates {
  status: 'candidates'
  claim: string
  normalized: { query: string }
  total_results: number
  cached: boolean
  coverage: {
    retrieved_studies: number
    full_text_available: number
    abstract_only: number
    metadata_only: number
  }
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
    metadata: {
      design: string
      population?: StudyPopulation
    }
    access: FullTextAccess
  }[]
}

/** One source behind a verdict. Shown as a tab in "Further reading". */
export interface Source {
  title: string
  publisher: string // e.g. "Journal of Food Protection · 2011"
  category: string // source category
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
