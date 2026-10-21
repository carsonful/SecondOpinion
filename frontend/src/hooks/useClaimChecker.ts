import { useState } from 'react'
import { VerdictData } from '../types'
import { EXAMPLE_CLAIMS } from '../data/exampleClaims'
import { hydrateExample } from '../data/hydrateExample'

export type Status = 'idle' | 'loading' | 'error' | 'success'

export function useClaimChecker() {
  const [claim, setClaim] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [verdict, setVerdict] = useState<VerdictData | null>(null)
  const [activeClaim, setActiveClaim] = useState('')

  async function checkClaim(text: string) {
    const trimmed = text.trim()
    if (!trimmed) return

    setStatus('loading')
    setErrorMessage('')

    const example = EXAMPLE_CLAIMS.find(({ claim }) => claim.toLowerCase() === trimmed.toLowerCase())

    try {
      const res = example
        ? await fetch(`/api/examples/${example.slug}`)
        : await fetch('/api/claims', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ claim: trimmed }),
          })

      if (!res.ok) {
        setErrorMessage(
          example
            ? 'This saved example is unavailable right now. Try again in a moment.'
            : res.status === 404
              ? 'No studies matched this claim.'
              : 'Something went wrong on our end. Try again in a moment.'
        )
        setStatus('error')
        return
      }

      const data = await res.json()
      setStatus('success')
      setActiveClaim(trimmed)
      setVerdict(example ? hydrateExample(data) : data)
    } catch {
      setErrorMessage("Can't reach the server right now.")
      setStatus('error')
    }
  }

  function reset() {
    setClaim('')
    setStatus('idle')
    setErrorMessage('')
    setVerdict(null)
    setActiveClaim('')
  }

  return { claim, setClaim, status, errorMessage, verdict, activeClaim, checkClaim, reset }
}
