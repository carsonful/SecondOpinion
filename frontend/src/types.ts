import { ReactNode } from 'react'

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