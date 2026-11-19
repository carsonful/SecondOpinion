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
  pmc_only: boolean
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
