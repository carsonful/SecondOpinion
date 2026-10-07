import { ReactNode } from 'react'

export interface VerdictData {
    verdict: string
    tag: string
    confidence: number
    chatBody: ReactNode
    relatedClaims?: string[]
}