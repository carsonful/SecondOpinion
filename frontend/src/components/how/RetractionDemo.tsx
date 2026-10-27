import { useEffect, useRef, useState } from 'react'

type Outcome = 'clear' | 'retracted' | 'concern' | 'corrected' | 'preprint'

// Sample records for the demo, not real papers.
const SOURCES: { title: string; meta: string; outcome: Outcome }[] = [
  { title: 'Randomized trial', meta: 'Journal article · 2022', outcome: 'clear' },
  { title: 'Nutrition blog-cited study', meta: 'Journal article · 2019', outcome: 'retracted' },
  { title: 'Cohort study', meta: 'Journal article · 2021', outcome: 'clear' },
  { title: 'Small pilot trial', meta: 'Journal article · 2018', outcome: 'concern' },
  { title: 'Survey of 2,000 adults', meta: 'Journal article · 2020', outcome: 'corrected' },
  { title: 'Lab study', meta: 'Preprint server · 2024', outcome: 'preprint' },
]

const RESULT: Record<Outcome, { label: string; detail: string; kept: boolean }> = {
  clear: { label: 'No notice found', detail: 'Included', kept: true },
  retracted: { label: 'Retracted', detail: 'Excluded, notice shown', kept: false },
  concern: { label: 'Expression of concern', detail: 'Withheld while unresolved', kept: false },
  corrected: { label: 'Correction issued', detail: 'Corrected version used', kept: true },
  preprint: { label: 'Preprint', detail: 'Shown separately', kept: false },
}

const STEP_MS = 520

interface DemoProps {
  /** Called with true once the scan has finished, false when it resets. */
  onStatusChange?: (done: boolean) => void
}

export default function RetractionDemo({ onStatusChange }: DemoProps) {
  // -1 = not started, 0..n-1 = scanning that row, n = finished
  const [cursor, setCursor] = useState(-1)
  const timer = useRef<number>()
  const running = cursor >= 0 && cursor < SOURCES.length
  const finished = cursor === SOURCES.length

  useEffect(() => {
    if (!running) return
    timer.current = window.setTimeout(() => setCursor((c) => c + 1), STEP_MS)
    return () => window.clearTimeout(timer.current)
  }, [cursor, running])

  useEffect(() => {
    onStatusChange?.(finished)
  }, [finished, onStatusChange])

  const kept = SOURCES.filter((s) => RESULT[s.outcome].kept).length

  return (
    <div className="demo">
      <p className="demo__caption">Planned screening · sample records</p>
      <ul className="retract__list">
        {SOURCES.map((s, i) => {
          const checked = cursor > i
          const scanning = cursor === i
          const r = RESULT[s.outcome]
          return (
            <li
              key={s.title}
              className={[
                'retract__row',
                scanning ? 'retract__row--scanning' : '',
                checked ? `retract__row--${s.outcome}` : '',
                checked && !r.kept ? 'retract__row--out' : '',
              ].join(' ')}
            >
              <div className="retract__source">
                <span className="retract__title">{s.title}</span>
                <span className="retract__meta">{s.meta}</span>
              </div>
              <div className="retract__status">
                {scanning && <span className="retract__spinner" aria-hidden="true" />}
                {checked && (
                  <>
                    <span className={`retract__badge retract__badge--${s.outcome}`}>{r.label}</span>
                    <span className="retract__detail">{r.detail}</span>
                  </>
                )}
              </div>
            </li>
          )
        })}
      </ul>

      <div className="retract__footer" aria-live="polite">
        {finished ? (
          <>
            <p className="retract__summary">
              <strong>
                {kept} of {SOURCES.length}
              </strong>{' '}
              sample sources pass this integrity screen.
            </p>
            <button type="button" className="demo__ghost" onClick={() => setCursor(-1)}>
              ↺ Reset
            </button>
          </>
        ) : (
          <button type="button" className="demo__run" onClick={() => setCursor(0)} disabled={running}>
            {running ? 'Checking notices…' : 'Run retraction check'}
          </button>
        )}
      </div>
    </div>
  )
}
