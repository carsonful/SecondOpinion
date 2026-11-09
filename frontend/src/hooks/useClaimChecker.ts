import { useRef, useState } from 'react'
import { ClaimCandidates, VerdictData } from '../types'

export type Status = 'idle' | 'loading' | 'error' | 'success'

function requestError(status: number): string {
  if (status === 422) return 'Enter one clear health claim of up to 2,000 characters.'
  if (status === 429) return 'Too many research requests. Please wait a moment before trying again.'
  if (status === 503) return 'An evidence service is unavailable. Try again shortly.'
  return 'Something went wrong on our end. Try again in a moment.'
}

export function useClaimChecker() {
  const [pmcOnly, setPmcOnly] = useState(true)
  const activePmcOnly = useRef(true)
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

    const searchPmcOnly = refresh ? activePmcOnly.current : pmcOnly
    activePmcOnly.current = searchPmcOnly
    const currentRequest = ++requestId.current

    setStatus('loading')
    setErrorMessage('')
    setVerdict(null)
    setCandidates(null)

    try {
      const res = await fetch(`/api/claims${refresh ? '?refresh=true' : ''}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim: trimmed, pmc_only: searchPmcOnly }),
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

  return { pmcOnly, setPmcOnly, claim, setClaim, status, errorMessage, verdict, candidates, activeClaim, checkClaim, reset }
}
