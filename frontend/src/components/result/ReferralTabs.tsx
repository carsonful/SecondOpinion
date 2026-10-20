import { KeyboardEvent, useId, useState } from 'react'
import { Source } from '../../types'

const TAB_TINTS = [
  { bg: '#0B1957', ink: '#ffffff' },
  { bg: '#9ECCFA', ink: '#0B1957' },
  { bg: '#F6E4C8', ink: '#0B1957' },
]

/** Short tab label: the site for public pages, "Review"/"Study" for research. */
function tabLabel(s: Source) {
  if (/synthesis|review/i.test(s.category)) return 'Review'
  if (/guidance/i.test(s.category)) return s.site.replace(/\.(gov|org|com)$/i, '').toUpperCase()
  return 'Study'
}

interface ReferralTabsProps {
  sources: Source[]
}

/** "Further reading": one referral sheet per source on a clipboard, switched with index tabs. */
export default function ReferralTabs({ sources }: ReferralTabsProps) {
  const [active, setActive] = useState(0)
  const base = useId()
  const current = sources[Math.min(active, sources.length - 1)]

  // Arrow keys move between tabs, the standard tablist pattern
  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const next = (active + (e.key === 'ArrowRight' ? 1 : -1) + sources.length) % sources.length
    setActive(next)
    document.getElementById(`${base}-tab-${next}`)?.focus()
  }

  return (
    <div className="referrals">
      <div className="referrals__board">
        <span className="referrals__clip" aria-hidden="true" />

        <div className="referrals__tabs" role="tablist" aria-label="Sources">
          {sources.map((s, i) => {
            const tint = TAB_TINTS[i % TAB_TINTS.length]
            const selected = i === active
            return (
              <button
                key={s.url}
                id={`${base}-tab-${i}`}
                type="button"
                role="tab"
                aria-selected={selected}
                aria-controls={`${base}-panel`}
                tabIndex={selected ? 0 : -1}
                className={selected ? 'referrals__tab referrals__tab--on' : 'referrals__tab'}
                style={selected ? undefined : { background: tint.bg, color: tint.ink }}
                onClick={() => setActive(i)}
                onKeyDown={onKeyDown}
              >
                {i + 1} · {tabLabel(s)}
              </button>
            )
          })}
        </div>

        <div className="referrals__stack">
          <span className="referrals__under referrals__under--2" aria-hidden="true" />
          <span className="referrals__under referrals__under--1" aria-hidden="true" />
          <div
            id={`${base}-panel`}
            role="tabpanel"
            aria-labelledby={`${base}-tab-${active}`}
            className="referrals__sheet"
            key={current.url}
          >
            <div className="referrals__head">
              <span>
                REFERRAL {active + 1} OF {sources.length}
              </span>
              <span>FURTHER READING</span>
            </div>
            <span className="referrals__cat">{current.category}</span>
            <strong className="referrals__title">{current.title}</strong>
            <span className="referrals__pub">{current.publisher}</span>
            <p className="referrals__take">
              <strong>Takeaway:</strong> {current.takeaway}
            </p>
            <div className="referrals__foot">
              <a className="referrals__open" href={current.url} target="_blank" rel="noreferrer">
                Read on {current.site} ↗
              </a>
              <span className="referrals__hand">doc’s orders: read it yourself</span>
            </div>
          </div>
        </div>
      </div>

      <div className="referrals__aside">
        <span className="search__kicker">FURTHER READING</span>
        <h3>Want to dig deeper?</h3>
        <p>
          Each tab is one source behind this verdict. Flip through them, and open the original to read it
          yourself.
        </p>
      </div>
    </div>
  )
}