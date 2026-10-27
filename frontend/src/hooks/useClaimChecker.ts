import { useRef, useState } from 'react'
import { ClaimCandidates, VerdictData } from '../types'
import { EXAMPLE_CLAIMS } from '../data/exampleClaims'
import { hydrateExample } from '../data/hydrateExample'

export type Status = 'idle' | 'loading' | 'error' | 'success'

function requestError(status: number, isExample: boolean): string {
  if (isExample) return 'This saved example is unavailable right now. Try again in a moment.'
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
      const res = example
        ? await fetch(`/api/examples/${example.slug}`)
        : await fetch(`/api/claims${refresh ? '?refresh=true' : ''}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ claim: trimmed }),
          })

      if (currentRequest !== requestId.current) return

      if (!res.ok) {
        setErrorMessage(requestError(res.status, Boolean(example)))
        setStatus('error')
        return
      }

      const data = await res.json()
      if (currentRequest !== requestId.current) return
      setStatus('success')
      setActiveClaim(trimmed)
      if (example) setVerdict(hydrateExample(data))
      else setCandidates(data)
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
