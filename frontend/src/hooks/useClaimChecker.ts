import { useState } from 'react'
import { VerdictData } from '../types'
import { MOCK_RESULTS } from '../data/mockResults'

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

    const mock = MOCK_RESULTS[trimmed.toLowerCase()]
    if (mock) {
      await new Promise((resolve) => setTimeout(resolve, 900))
      setStatus('success')
      setActiveClaim(trimmed)
      setVerdict(mock)
      return
    }

    try {
      const res = await fetch('/api/claims', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim: trimmed }),
      })

      if (!res.ok) {
        setErrorMessage(
          res.status === 404
            ? 'No studies matched this claim.'
            : 'Something went wrong on our end. Try again in a moment.'
        )
        setStatus('error')
        return
      }

      const data = await res.json()
      setStatus('success')
      setActiveClaim(trimmed)
      setVerdict(data)
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
