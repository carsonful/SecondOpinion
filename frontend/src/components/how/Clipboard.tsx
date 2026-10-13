import { ReactNode } from 'react'

interface ClipboardProps {
  /** Small header on the sheet, e.g. "LAB REPORT · TEST 01" */
  label: string
  /** Right side of the header, e.g. "CLAIM INTAKE" */
  title: string
  /** Text of the ink stamp, e.g. "NORMALIZED" */
  stamp: string
  tone: 'green' | 'blue' | 'red'
  /** The stamp lands once this is true */
  stamped: boolean
  tilt?: number
  children: ReactNode
}

/** A glass clipboard holding a paper lab report. Paper and clip look the same in both themes. */
export default function Clipboard({ label, title, stamp, tone, stamped, tilt = 0, children }: ClipboardProps) {
  return (
    <div className="clipboard glass-card" style={{ transform: `rotate(${tilt}deg)` }}>
      <span className="clipboard__clip" aria-hidden="true" />
      <div className="clipboard__sheet">
        <div className="clipboard__head">
          <span>{label}</span>
          {/* the stamp lands where the title is, like a real stamp over a field */}
          <span className={stamped ? 'clipboard__title clipboard__title--covered' : 'clipboard__title'}>{title}</span>
        </div>
        {children}
        {stamped && (
          <span className={`clipboard__stamp clipboard__stamp--${tone}`} aria-hidden="true">
            {stamp}
          </span>
        )}
      </div>
    </div>
  )
}