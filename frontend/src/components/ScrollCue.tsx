import { useEffect, useState } from 'react'
import './ScrollCue.css'

interface ScrollCueProps {
  /** id of the first clipboard section, e.g. "board-synthesis". */
  targetId: string
  papers: number
  /** Scrolls to the clipboards (the results page already has goToBoard for this). */
  onGo: () => void
}

/**
 * A floating pill that tells people the papers (the clipboards) are further down the page,
 * since the summary panel fills the first screen. Clicking it scrolls there. It hides itself
 * for good once the clipboards come into view, or when dismissed.
 */
export default function ScrollCue({ targetId, papers, onGo }: ScrollCueProps) {
  const [reached, setReached] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    const target = document.getElementById(targetId)
    if (!target || typeof IntersectionObserver === 'undefined') return
    // "Reached" = the clipboards have entered the top three quarters of the screen.
    const observer = new IntersectionObserver(
      entries => { if (entries.some(entry => entry.isIntersecting)) setReached(true) },
      { rootMargin: '0px 0px -25% 0px' },
    )
    observer.observe(target)
    return () => observer.disconnect()
  }, [targetId])

  if (reached || dismissed) return null

  return (
    <div className="scroll-cue" role="region" aria-label="More below">
      <button type="button" className="scroll-cue__go" onClick={onGo}>
        <span className="scroll-cue__arrow" aria-hidden="true">↓</span>
        <span className="scroll-cue__text">
          <strong>{papers} {papers === 1 ? 'paper' : 'papers'} below</strong>
          <span>Browse the study clipboards</span>
        </span>
      </button>
      <button type="button" className="scroll-cue__close" aria-label="Dismiss" onClick={() => setDismissed(true)}>×</button>
    </div>
  )
}