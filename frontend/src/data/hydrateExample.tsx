import { VerdictData } from '../types'

interface ExplanationPart {
  text: string
  url?: string
  emphasis?: boolean
}

interface SavedExample extends Omit<VerdictData, 'chatBody'> {
  claim: string
  explanation: ExplanationPart[]
}

/** Turn the JSON explanation into the existing result component's React content. */
export function hydrateExample(data: SavedExample): VerdictData {
  return {
    verdict: data.verdict,
    tag: data.tag,
    confidence: data.confidence,
    sources: data.sources,
    relatedClaims: data.relatedClaims,
    chatBody: (
      <p>
        {data.explanation.map((part, index) =>
          part.url ? (
            <a key={index} href={part.url} target="_blank" rel="noreferrer">{part.text}</a>
          ) : part.emphasis ? (
            <em key={index}>{part.text}</em>
          ) : (
            part.text
          ),
        )}
      </p>
    ),
  }
}
