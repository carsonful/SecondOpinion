export interface ReportedMeasure {
  reported: string
  passage: string
}

export interface StudyAssessment {
  pmid: string
  category: string
  base_weight: number | null
  weight_version: 'base_weights_v0.1'
  eligibility: 'excluded' | 'withheld' | 'separate'
  eligibility_reason: string
  effective_weight: number
  flags: string[]
  assessment_status: 'pending' | 'completed' | 'unavailable' | 'skipped'
  summary: string | null
  measurement_warnings: string[]
  sample_sizes: ReportedMeasure[]
  effect_estimates: ReportedMeasure[]
  supporting_passages: string[]
  relevance: 'not_assessed' | 'relevant' | 'not_relevant' | 'uncertain'
  finding: 'not_assessed' | 'supports' | 'contradicts' | 'mixed' | 'inconclusive' | 'cannot_determine'
}

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
  integrity_links: { relation: string; pmid: string | null; citation: string | null; note: string | null }[]
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
  search_scope: 'claim' | 'intervention_only'
  assessments: StudyAssessment[]
  assessment_status: 'pending'
}
