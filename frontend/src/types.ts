export interface PubMedArticle {
  pmid: string
  title: string
  abstract: string | null
  journal: string | null
  year: number | null
  authors: string[]
  doi: string | null
  pmc_id: string | null
  publication_types: string[]
  mesh_terms: string[]
  retracted: boolean
  url: string
}

export interface ClaimResult {
  claim: string
  normalized: {
    query: string
    intervention: string
    outcome: string
    population: string | null
    relation: string
    negated: boolean
    version: 'foundry-v1'
  }
  evidence: {
    query: string
    query_translation: string | null
    total_results: number
    articles: PubMedArticle[]
  }
  assessment_status: 'pending'
}
