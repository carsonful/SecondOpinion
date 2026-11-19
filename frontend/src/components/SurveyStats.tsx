import { CSSProperties, useMemo, useState } from 'react'
import './SurveyStats.css'

/**
 * Shown while the AI overview is being written (it takes the longest). A little game: guess what
 * % of our survey respondents said something, lock it in, see the real number, rack up points.
 * All figures are % of the 58 adults and were re-checked against the Nov 14, 2026 export.
 * Update SURVEY_N and the answers below together when new responses come in.
 */
const SURVEY_N = 58
const MAX_PER_ROUND = 100

interface Round {
  q: string // finishes the sentence "What % of people ..."
  answer: number // whole percent, as shown in the survey write-up
  note: string // one line shown after the reveal
}

const ROUNDS: Round[] = [
  { q: 'Google a health claim first when they wonder if it’s true', answer: 62, note: 'Search is still the front door.' },
  { q: 'try an AI chatbot first for a health claim', answer: 28, note: 'And only 24% trust one a lot or completely.' },
  { q: 'say social media is where they mostly see health claims', answer: 84, note: 'Yet just 3% trust it a lot or completely.' },
  { q: 'trust a doctor or pharmacist a lot or completely', answer: 83, note: 'Doctors still win on trust.' },
  { q: 'changed a diet, supplement or routine in the last year because of something they saw online', answer: 47, note: 'Almost half. Claims change what people do.' },
  { q: 'named too many conflicting answers as a top frustration when checking claims', answer: 60, note: 'The internet disagrees with itself.' },
  { q: 'said a cited study or a source link they can open makes them believe a claim', answer: 64, note: 'That is what Second Opinion puts up front.' },
  { q: 'trust social media a lot or completely for health claims', answer: 3, note: 'Seen everywhere, trusted almost nowhere.' },
]

type Tier = 'hit' | 'close' | 'ok' | 'off' | 'whoa'

function tierFor(miss: number): { tier: Tier; label: string; icon: string } {
  if (miss === 0) return { tier: 'hit', label: 'BULLSEYE', icon: '🎯' }
  if (miss <= 5) return { tier: 'close', label: 'SO CLOSE', icon: '🔥' }
  if (miss <= 15) return { tier: 'ok', label: 'NOT BAD', icon: '👀' }
  if (miss <= 30) return { tier: 'off', label: 'OFF A BIT', icon: '😅' }
  return { tier: 'whoa', label: 'WHOA', icon: '🤯' }
}

function pointsFor(miss: number): number {
  return Math.max(0, MAX_PER_ROUND - Math.round(miss * 3))
}

// Ranks, from the average miss across all rounds. Georgie is the team's HR dog, so she gets the bottom rung.
const RANKS = [
  { max: 6, range: '0–6 off', title: 'Certified Mythbuster', icon: '🏆', line: 'You read people (and the internet) like a pro.' },
  { max: 12, range: '7–12 off', title: 'Sharp Intern', icon: '🧠', line: 'Solid instincts. Promotion pending.' },
  { max: 20, range: '13–20 off', title: 'Group-Project Gambler', icon: '🎲', line: 'Vibes carried you. Mostly.' },
  { max: Infinity, range: '21+ off', title: 'Georgie, Head of HR', icon: '🐕', line: 'Confident, adorable, wrong. Treats for effort.' },
]

function rankIndex(avgMiss: number): number {
  return RANKS.findIndex(r => avgMiss <= r.max)
}

function shuffled<T>(items: T[]): T[] {
  const copy = [...items]
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy
}

// Deterministic confetti so it doesn't jump around on re-render.
const CONFETTI = Array.from({ length: 16 }, (_, k) => {
  const angle = (k / 16) * Math.PI * 2 + (k % 3) * 0.2
  const dist = 46 + (k % 4) * 14
  return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist - 18, hue: (k * 47) % 360, delay: (k % 5) * 0.02 }
})

type Vars = CSSProperties & Record<`--${string}`, string | number>

export default function SurveyStats() {
  const [order, setOrder] = useState(() => shuffled(ROUNDS))
  const [i, setI] = useState(0)
  const [guess, setGuess] = useState(50)
  const [locked, setLocked] = useState(false)
  const [results, setResults] = useState<{ miss: number; points: number }[]>([])

  const done = i >= order.length
  const round = order[i]
  const miss = locked && round ? Math.abs(guess - round.answer) : 0
  const tier = tierFor(miss)
  const score = results.reduce((a, r) => a + r.points, 0)
  const total = order.length * MAX_PER_ROUND
  const avgMiss = useMemo(
    () => (results.length ? Math.round(results.reduce((a, r) => a + r.miss, 0) / results.length) : 0),
    [results],
  )
  const rankIdx = rankIndex(avgMiss)
  const rank = RANKS[rankIdx]
  const started = results.length > 0

  function lockIn() {
    const m = Math.abs(guess - round.answer)
    setLocked(true)
    setResults(r => [...r, { miss: m, points: pointsFor(m) }])
  }
  function next() {
    setI(n => n + 1)
    setGuess(50)
    setLocked(false)
  }
  function again() {
    setOrder(shuffled(ROUNDS))
    setI(0)
    setGuess(50)
    setLocked(false)
    setResults([])
  }

  const lo = locked ? Math.min(guess, round.answer) : guess
  const hi = locked ? Math.max(guess, round.answer) : guess
  const trackVars: Vars = { '--pct': lo / 100, '--ans': locked ? round.answer / 100 : 0, '--lo': lo / 100, '--hi': hi / 100 }

  return (
    <aside className="survey-stats" aria-label="Guess our survey results, while you wait">
      <div className="survey-stats__head">
        <span className="survey-stats__badge">
          <span aria-hidden="true">🎮</span> GUESS THE SURVEY
        </span>
        <span className="survey-stats__score" aria-label={`Score ${score} points`}>
          <span aria-hidden="true">⭐</span> <b key={score}>{score}</b> pts
        </span>
      </div>

      <div className="survey-stats__pips" role="img" aria-label={done ? 'All rounds played' : `Round ${i + 1} of ${order.length}`}>
        {order.map((_, k) => (
          <span key={k} className={k < i || (k === i && locked) ? 'is-done' : k === i && !done ? 'is-now' : undefined} />
        ))}
      </div>

      {!done && (
        <div className={`survey-stats__game${locked && tier.tier === 'whoa' ? ' is-shake' : ''}`} key={i}>
          <p className="survey-stats__round">
            ROUND {i + 1} <span>/ {order.length}</span> · {SURVEY_N} people surveyed
          </p>
          <p className="survey-stats__q" id="survey-q">
            What % of people <strong>{round.q}</strong>?
          </p>

          <div className="survey-stats__stage">
            <div className="survey-stats__guesswrap">
              <span className="survey-stats__guesslabel">YOUR GUESS</span>
              <output className="survey-stats__guess" htmlFor="survey-guess" key={locked ? 'locked' : guess}>
                {guess}%
              </output>
            </div>

            <div className={`survey-stats__track${locked ? ' is-locked' : ''}`} style={trackVars}>
              <input
                id="survey-guess"
                type="range"
                min={0}
                max={100}
                step={1}
                value={guess}
                disabled={locked}
                aria-labelledby="survey-q"
                aria-valuetext={`${guess} percent`}
                onChange={e => setGuess(Number(e.target.value))}
              />
              {locked && <span className="survey-stats__lead" aria-hidden="true" />}
              {locked && <span className="survey-stats__gap" aria-hidden="true" />}
              {locked && (
                <span className="survey-stats__pin" aria-hidden="true">
                  <span>{round.answer}%</span>
                </span>
              )}
            </div>
            <div className="survey-stats__scale" aria-hidden="true">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>

          {!locked ? (
            <div className="survey-stats__foot">
              <span className="survey-stats__tip">Drag the dial or use the arrow keys.</span>
              <button type="button" className="survey-stats__btn survey-stats__btn--main" onClick={lockIn}>
                Lock it in <span aria-hidden="true">🔒</span>
              </button>
            </div>
          ) : (
            <div className="survey-stats__reveal" role="status">
              <div className="survey-stats__result">
                <span className={`survey-stats__stamp survey-stats__stamp--${tier.tier}`}>
                  <span aria-hidden="true">{tier.icon}</span> {tier.label}
                </span>
                <span className="survey-stats__points">+{results[results.length - 1]?.points ?? 0}</span>
                {!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches && miss <= 5 && (
                  <span className="survey-stats__confetti" aria-hidden="true">
                    {CONFETTI.map((c, k) => (
                      <i key={k} style={{ '--x': `${c.x}px`, '--y': `${c.y}px`, '--h': c.hue, animationDelay: `${c.delay}s` } as Vars} />
                    ))}
                  </span>
                )}
              </div>
              <p>
                <strong>{round.answer}%</strong> actually did. You said {guess}%, {miss === 0 ? 'bang on' : `${miss} point${miss === 1 ? '' : 's'} off`}. {round.note}
              </p>
              <button type="button" className="survey-stats__btn survey-stats__btn--main" onClick={next} autoFocus>
                {i + 1 < order.length ? 'Next round' : 'See my rank'} <span aria-hidden="true">→</span>
              </button>
            </div>
          )}
        </div>
      )}

      {done && (
        <div className="survey-stats__game survey-stats__done" role="status">
          <span className="survey-stats__trophy" aria-hidden="true">
            {rank.icon}
          </span>
          <p className="survey-stats__ranklabel">YOUR RANK</p>
          <p className="survey-stats__rank">{rank.title}</p>
          <p className="survey-stats__final">
            <b>{score}</b> / {total} pts · off by {avgMiss} points on average
          </p>
          <p className="survey-stats__note">{rank.line}</p>
          <div className="survey-stats__foot">
            <span className="survey-stats__tip">Your overview will pop in above when it’s ready.</span>
            <button type="button" className="survey-stats__btn survey-stats__btn--main" onClick={again}>
              Play again <span aria-hidden="true">↻</span>
            </button>
          </div>
        </div>
      )}

      <div className="survey-stats__ranks">
        <p className="survey-stats__rankshead">
          RANKS <span>· based on your average miss{started && !done ? ' so far' : ''}</span>
        </p>
        <ul>
          {RANKS.map((r, k) => (
            <li key={r.title} className={started && k === rankIdx ? 'is-you' : undefined} aria-current={started && k === rankIdx ? 'true' : undefined}>
              <span className="survey-stats__rankicon" aria-hidden="true">{r.icon}</span>
              <span className="survey-stats__ranktext">
                <b>{r.title}</b>
                <small>{r.range}</small>
              </span>
              {started && k === rankIdx && <em>{done ? 'you' : 'on track'}</em>}
            </li>
          ))}
        </ul>
      </div>

      <p className="survey-stats__source">Source: Second Opinion team survey (Qualtrics), n = {SURVEY_N} adults.</p>
    </aside>
  )
}