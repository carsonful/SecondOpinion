import { useEffect, useState } from 'react'

type Role = 'subject' | 'comparison' | 'outcome'

interface Example {
  label: string
  // The messy input, split into pieces. Pieces with a role get highlighted.
  pieces: { text: string; role?: Role }[]
  parts: Record<Role, string>
  normalized: string
}

// Sample claims for the demo only. The real normalization runs on the backend.
const EXAMPLES: Example[] = [
  {
    label: 'Raw milk',
    pieces: [
      { text: 'my aunt swears ' },
      { text: 'raw milk', role: 'subject' },
      { text: ' is wayyy ' },
      { text: 'healthier', role: 'outcome' },
      { text: ' than ' },
      { text: 'the store stuff', role: 'comparison' },
      { text: '??' },
    ],
    parts: {
      subject: 'Raw (unpasteurized) milk',
      comparison: 'Pasteurized milk',
      outcome: 'Nutritional value',
    },
    normalized: 'Is raw milk more nutritious than pasteurized milk?',
  },
  {
    label: 'Knuckles',
    pieces: [
      { text: 'does ' },
      { text: 'cracking ur knuckles', role: 'subject' },
      { text: ' give u ' },
      { text: 'arthritis', role: 'outcome' },
      { text: ' fr' },
    ],
    parts: {
      subject: 'Habitual knuckle cracking',
      comparison: 'Not cracking knuckles',
      outcome: 'Hand osteoarthritis',
    },
    normalized: 'Does habitual knuckle cracking cause hand osteoarthritis?',
  },
  {
    label: 'Cold showers',
    pieces: [
      { text: 'ice cold showers', role: 'subject' },
      { text: ' every morning = ' },
      { text: 'never getting sick again', role: 'outcome' },
    ],
    parts: {
      subject: 'Cold showers',
      comparison: 'Warm or usual showers',
      outcome: 'How often people get sick',
    },
    normalized: 'Do cold showers reduce how often people get sick?',
  },
]

const ROLE_LABEL: Record<Role, string> = {
  subject: 'What',
  comparison: 'Compared to',
  outcome: 'Effect on',
}

interface DemoProps {
  /** Called with true once the demo has been run, false when it resets. */
  onStatusChange?: (done: boolean) => void
}

export default function NormalizeDemo({ onStatusChange }: DemoProps) {
  const [index, setIndex] = useState(0)
  const [done, setDone] = useState(false)

  useEffect(() => {
    onStatusChange?.(done)
  }, [done, onStatusChange])
  // Bumping the key restarts the reveal animation each time.
  const [runId, setRunId] = useState(0)
  const ex = EXAMPLES[index]

  function pick(i: number) {
    setIndex(i)
    setDone(false)
  }

  function run() {
    setDone(true)
    setRunId((n) => n + 1)
  }

  return (
    <div className="demo">
      <div className="demo__tabs" role="tablist" aria-label="Sample claims">
        {EXAMPLES.map((e, i) => (
          <button
            key={e.label}
            type="button"
            role="tab"
            aria-selected={i === index}
            className="demo__tab"
            onClick={() => pick(i)}
          >
            {e.label}
          </button>
        ))}
      </div>

      <p className="demo__caption">What someone types</p>
      <p className={`norm__messy ${done ? 'norm__messy--marked' : ''}`}>
        “
        {ex.pieces.map((p, i) =>
          p.role ? (
            <mark key={i} className={`norm__mark norm__mark--${p.role}`}>
              {p.text}
            </mark>
          ) : (
            <span key={i}>{p.text}</span>
          ),
        )}
        ”
      </p>

      {!done ? (
        <button type="button" className="demo__run" onClick={run}>
          Normalize it
        </button>
      ) : (
        <div key={runId} className="norm__result" aria-live="polite">
          <div className="norm__parts">
            {(Object.keys(ROLE_LABEL) as Role[]).map((role, i) => (
              <div
                key={role}
                className={`norm__part norm__part--${role}`}
                style={{ animationDelay: `${i * 180}ms` }}
              >
                <span className="norm__part-label">{ROLE_LABEL[role]}</span>
                <span className="norm__part-value">{ex.parts[role]}</span>
              </div>
            ))}
          </div>
          <div className="norm__final" style={{ animationDelay: '620ms' }}>
            <span className="demo__caption">What we search for</span>
            <p>{ex.normalized}</p>
          </div>
          <button type="button" className="demo__ghost" onClick={() => setDone(false)}>
            ↺ Reset
          </button>
        </div>
      )}
    </div>
  )
}