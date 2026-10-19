import { useEffect, useRef, useState } from 'react'
import { ClaimResult } from '../types'

export type Status = 'idle' | 'loading' | 'error' | 'success'

export function useClaimChecker() {
  const [claim, setClaim] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [result, setResult] = useState<ClaimResult | null>(null)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  async function checkClaim(text: string) {
    const trimmed = text.trim()
    if (!trimmed) return
    controller.current?.abort()
    const request = new AbortController()
    controller.current = request
    setClaim(trimmed)
    setResult(null)
    setStatus('loading')
    setErrorMessage('')

    try {
      const res = await fetch('/api/claims', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim: trimmed }),
        signal: request.signal,
      })
      if (request.signal.aborted) return
      if (!res.ok) {
        const message = res.status === 422
          ? 'Enter one clear health claim of up to 2,000 characters.'
          : res.status === 502 || res.status === 503
            ? 'A research service is unavailable. Please try again shortly.'
            : 'Something went wrong on our end. Please try again.'
        throw new Error(message)
      }
      const data: ClaimResult = await res.json()
      if (request.signal.aborted) return
      setResult(data)
      setStatus('success')
    } catch (error) {
      if (request.signal.aborted) return
      setErrorMessage(error instanceof TypeError
        ? "Can't reach the server right now."
        : error instanceof Error ? error.message : 'Unable to load studies.')
      setStatus('error')
    }
  }

  function reset() {
    controller.current?.abort()
    setClaim('')
    setStatus('idle')
    setErrorMessage('')
    setResult(null)
  }

  return { claim, setClaim, status, errorMessage, result, checkClaim, reset }
}
