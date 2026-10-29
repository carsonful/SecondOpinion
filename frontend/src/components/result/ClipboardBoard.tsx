import { CSSProperties, KeyboardEvent, ReactNode, useEffect, useId, useRef, useState } from 'react'

/** Colours for one clipboard: tab pair, stamp ink, and the rgb used for the board's tinted edge. */
export interface ClipboardTint {
  rgb: string
  tab: string
  tabInk: string
  tabAlt: string
  tabAltInk: string
  stamp: string
}

export interface ClipboardTab {
  id: string
  label: string
}

interface ClipboardBoardProps {
  tabs: ClipboardTab[]
  activeId: string
  onSelect: (id: string) => void
  /** Accessible name for the tab strip, e.g. "Trials". */
  label: string
  /** Small caption on the left of the sheet's header line. */
  caption: string
  tint: ClipboardTint
  /** Ink stamp for the active sheet. It lands when the board scrolls into view, and again on every tab change. */
  stamp?: { big: string; sub: string }
  asideKicker: string
  asideTitle: string
  asideText: string
  /** The active tab's content. */
  children: ReactNode
}

/** A clipboard with index tabs: one paper sheet per item, switched with the tabs. */
export default function ClipboardBoard({
  tabs, activeId, onSelect, label, caption, tint, stamp, asideKicker, asideTitle, asideText, children,
}: ClipboardBoardProps) {
  const base = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const [seen, setSeen] = useState(false)
  const activeIndex = Math.max(0, tabs.findIndex(tab => tab.id === activeId))

  // The stamp lands once the board is actually on screen, so the reader sees it happen.
  useEffect(() => {
    const node = rootRef.current
    if (!node || typeof IntersectionObserver === 'undefined') { setSeen(true); return }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setSeen(true); observer.disconnect() }
    }, { threshold: 0.45 })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  // Arrow keys move between tabs, the standard tablist pattern
  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const next = (activeIndex + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
    onSelect(tabs[next].id)
    document.getElementById(`${base}-tab-${next}`)?.focus()
  }

  const vars = { '--tint': tint.rgb, '--stamp': tint.stamp } as CSSProperties

  return (
    <div className="referrals" style={vars} ref={rootRef}>
      <div className="referrals__board">
        <span className="referrals__clip" aria-hidden="true" />

        <div className="referrals__tabs" role="tablist" aria-label={label}>
          {tabs.map((tab, i) => {
            const selected = i === activeIndex
            const alt = i % 2 === 1
            return (
              <button
                key={tab.id}
                id={`${base}-tab-${i}`}
                type="button"
                role="tab"
                aria-selected={selected}
                aria-controls={`${base}-panel`}
                tabIndex={selected ? 0 : -1}
                className={selected ? 'referrals__tab referrals__tab--on' : 'referrals__tab'}
                style={selected ? undefined : { background: alt ? tint.tabAlt : tint.tab, color: alt ? tint.tabAltInk : tint.tabInk }}
                onClick={() => onSelect(tab.id)}
                onKeyDown={onKeyDown}
              >
                {tab.label}
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
            aria-labelledby={`${base}-tab-${activeIndex}`}
            className="referrals__sheet"
          >
            <div className="referrals__head">
              <span>{caption}</span>
            </div>
            {seen && stamp && (
              <span key={`stamp-${activeId}`} className="referrals__stamp" aria-hidden="true">
                <b>{stamp.big}</b>
                <i>{stamp.sub}</i>
              </span>
            )}
            {children}
          </div>
        </div>
      </div>

      <div className="referrals__aside">
        <span className="search__kicker">{asideKicker}</span>
        <h3>{asideTitle}</h3>
        <p>{asideText}</p>
      </div>
    </div>
  )
}