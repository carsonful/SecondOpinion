import { useRef, useState } from 'react'
import { ClaimCandidates, VerdictData } from '../types'
import { EXAMPLE_CLAIMS } from '../data/exampleClaims'
import { hydrateExample } from '../data/hydrateExample'

export type Status = 'idle' | 'loading' | 'error' | 'success'

function requestError(status: number): string {
  if (status === 422) return 'Enter one clear health claim of up to 2,000 characters.'
  if (status === 503) return 'An evidence service is unavailable. Try again shortly.'
  return 'Something went wrong on our end. Try again in a moment.'
}

export function useClaimChecker() {
  const [claim, setClaim] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [verdict, setVerdict] = useState<VerdictData | null>(null)
  const [activeClaim, setActiveClaim] = useState('')
  const [candidates, setCandidates] = useState<ClaimCandidates | null>(null)
  const requestId = useRef(0)

  async function checkClaim(text: string, refresh = false) {
    const trimmed = text.trim()
    if (!trimmed) return

    const currentRequest = ++requestId.current

    setStatus('loading')
    setErrorMessage('')
    setVerdict(null)
    setCandidates(null)

    const example = EXAMPLE_CLAIMS.find(({ claim }) => claim.toLowerCase() === trimmed.toLowerCase())

    try {
      // Saved examples come from Postgres. If they can't be loaded for any reason,
      // fall through to a live search so the example buttons always work.
      if (example && !refresh) {
        try {
          const saved = await fetch(`/api/examples/${example.slug}`)
          if (currentRequest !== requestId.current) return
          if (saved.ok) {
            const data = await saved.json()
            if (currentRequest !== requestId.current) return
            setStatus('success')
            setActiveClaim(trimmed)
            setVerdict(hydrateExample(data))
            return
          }
        } catch {
          // Fall through to the live search below.
        }
      }

      const res = await fetch(`/api/claims${refresh ? '?refresh=true' : ''}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim: trimmed }),
      })

      if (currentRequest !== requestId.current) return

      if (!res.ok) {
        setErrorMessage(requestError(res.status))
        setStatus('error')
        return
      }

      const data = await res.json()
      if (currentRequest !== requestId.current) return
      setStatus('success')
      setActiveClaim(trimmed)
      setCandidates(data)
    } catch {
      if (currentRequest !== requestId.current) return
      setErrorMessage("Can't reach the server right now.")
      setStatus('error')
    }
  }

  function reset() {
    requestId.current++
    setClaim('')
    setStatus('idle')
    setErrorMessage('')
    setVerdict(null)
    setActiveClaim('')
    setCandidates(null)
  }

  return { claim, setClaim, status, errorMessage, verdict, candidates, activeClaim, checkClaim, reset }
}
