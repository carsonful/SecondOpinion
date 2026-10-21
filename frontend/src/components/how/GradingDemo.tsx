import { useEffect, useState } from 'react'

// Rules mirror docs/evidence-grading.md (Carson's grading method, PR #52).
// Keep the two in sync if the method changes.
const TYPES = [
  {
    id: 'rct',
    tag: 'Randomized Controlled Trial',
    category: 'Randomized evidence',
    note: 'Good for testing whether something causes an effect. Randomizing doesn’t guarantee the study was run well.',
  },
  {
    id: 'trial',
    tag: 'Clinical Trial',
    category: 'Intervention evidence',
    note: 'Researchers tested an intervention, but randomization is unknown unless it’s explicitly tagged.',
  },
  {
    id: 'obs',
    tag: 'Observational Study',
    category: 'Observational evidence',
    note: 'Useful for spotting associations and harms. Other factors can muddy cause and effect.',
  },
  {
    id: 'sr',
    tag: 'Systematic Review / Meta-Analysis',
    category: 'Research synthesis',
    note: 'Pulls many studies together. Only as strong as its methods and the studies inside it, so it doesn’t get an automatic top grade.',
  },
  {
    id: 'review',
    tag: 'Review',
    category: 'General review',
    note: 'Good background, but no systematic search or appraisal behind it.',
  },
  {
    id: 'case',
    tag: 'Case Report',
    category: 'Descriptive evidence',
    note: 'Can flag unusual events, but can’t tell you how common or how big an effect is.',
  },
  {
    id: 'comment',
    tag: 'Editorial / Letter',
    category: 'Commentary',
    note: 'Usually discussion, not original research. We read the abstract before assuming anything.',
  },
  {
    id: 'unknown',
    tag: 'Missing / conflicting',
    category: 'Unclassified',
    note: 'The design is unclear. That’s not the same as low quality, so it isn’t penalized.',
  },
] as const

interface DemoProps {
  /** Called with true once the viewer has graded something. */
  onStatusChange?: (done: boolean) => void
}

export default function GradingDemo({ onStatusChange }: DemoProps) {
  const [typeId, setTypeId] = useState<string>('rct')
  const [touched, setTouched] = useState(false)

  useEffect(() => {
    onStatusChange?.(touched)
  }, [touched, onStatusChange])
  const [animalsOnly, setAnimalsOnly] = useState(false)
  const [preprint, setPreprint] = useState(false)
  const type = TYPES.find((t) => t.id === typeId) ?? TYPES[0]

  const flags: { text: string; tone: 'info' | 'warn' }[] = []
  if (animalsOnly) flags.push({ text: 'Preclinical: animal study, shown separately', tone: 'warn' })
  if (preprint) flags.push({ text: 'Preprint: not yet peer reviewed, shown separately', tone: 'warn' })
  if (!animalsOnly) flags.push({ text: 'Humans: applies to people', tone: 'info' })

  return (
    <div className="demo">
      <p className="demo__caption">1. What kind of study is it?</p>
      <div className="grade__types">
        {TYPES.map((t) => (
          <button
            key={t.id}
            type="button"
            className="grade__type"
            aria-pressed={t.id === typeId}
            onClick={() => {
              setTypeId(t.id)
              setTouched(true)
            }}
          >
            {t.tag}
          </button>
        ))}
      </div>

      <p className="demo__caption">2. Anything else on the record?</p>
      <div className="grade__toggles">
        <label className="grade__toggle">
          <input type="checkbox" checked={animalsOnly} onChange={(e) => {
              setAnimalsOnly(e.target.checked)
              setTouched(true)
            }} />
          <span>Animals only</span>
        </label>
        <label className="grade__toggle">
          <input type="checkbox" checked={preprint} onChange={(e) => {
              setPreprint(e.target.checked)
              setTouched(true)
            }} />
          <span>Preprint</span>
        </label>
      </div>

      <div className="grade__card" key={`${typeId}-${animalsOnly}-${preprint}`} aria-live="polite">
        <span className="demo__caption">Graded as</span>
        <p className="grade__category">{animalsOnly ? 'Preclinical evidence' : type.category}</p>
        <p className="grade__note">{type.note}</p>
        <div className="grade__flags">
          {flags.map((f) => (
            <span key={f.text} className={`grade__flag grade__flag--${f.tone}`}>
              {f.text}
            </span>
          ))}
        </div>
      </div>

      <p className="demo__footnote">
        Whether a study agrees with the claim never changes its grade. Grading is about how the study was
        done, not what it found.
      </p>
    </div>
  )
}