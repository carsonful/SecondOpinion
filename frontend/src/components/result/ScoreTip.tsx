import { useEffect, useId, useRef, useState } from 'react'

interface ScoreTipProps {
  onHowItWorks?: () => void
}

/**
 * The "?" next to the confidence score. Opens on hover, on keyboard focus,
 * or on tap (for phones). Escape or a tap outside closes it.
 */
export default function ScoreTip({ onHowItWorks }: ScoreTipProps) {
  const [pinned, setPinned] = useState(false)
  const id = useId()
  const wrap = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!pinned) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setPinned(false)
    }
    function onClick(e: MouseEvent) {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setPinned(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onClick)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClick)
    }
  }, [pinned])

  return (
    <span ref={wrap} className={pinned ? 'scoretip scoretip--open' : 'scoretip'}>
      <button
        type="button"
        className="scoretip__btn"
        aria-label="How the score is calculated"
        aria-describedby={id}
        aria-expanded={pinned}
        onClick={() => setPinned((p) => !p)}
      >
        ?
      </button>
      <span id={id} role="tooltip" className="scoretip__card">
        <strong className="scoretip__title">How this score works</strong>
        <span className="scoretip__text">It reflects how strong the evidence behind the verdict is:</span>
        <span className="scoretip__list">
          <span>
            <i style={{ background: '#2a6cb8' }} />
            what kinds of studies there are
          </span>
          <span>
            <i style={{ background: '#D6B482' }} />
            how consistently they agree
          </span>
          <span>
            <i style={{ background: '#0B1957' }} />
            whether any were retracted or flagged
          </span>
        </span>
        <span className="scoretip__note">
          Animal studies and preprints don’t count toward it. It’s a guide, not a guarantee.
        </span>
        {onHowItWorks && (
          <button type="button" className="scoretip__link" onClick={onHowItWorks}>
            See how it works →
          </button>
        )}
      </span>
    </span>
  )
}