import { useEffect, useMemo, useState } from 'react'
import './LoadingTips.css'

/** Silly status words, shown with a trailing ellipsis. */
const VERBS = [
  'Combobulating',
  'Discombobulating',
  'Recombobulating',
  'Consulting the lab coat',
  'Squinting at abstracts',
  'Peer-reviewing the vibes',
  'Asking PubMed nicely',
  'Alphabetizing the evidence',
  'Washing hands (20 seconds)',
  'Calibrating the stethoscope',
  'Un-doomscrolling',
  'Reading the fine print',
  'Cross-referencing',
  'Skimming so you don’t have to',
  'Defragmenting the literature',
  'Putting on the safety goggles',
]

interface Tip {
  kicker: string
  /** Optional big number shown before the text. */
  stat?: string
  text: string
}

/** Survey size. Update this and the numbers below together when new responses come in. */
const SURVEY_N = 58
const SURVEY = `FROM OUR SURVEY OF ${SURVEY_N} PEOPLE`
const FUN = 'DID YOU KNOW'
const DOC = 'DOC’S ORDERS'

const TIPS: Tip[] = [
  // Real numbers from our Qualtrics survey (export of Oct 29, 2026; 58 valid responses)
  { kicker: SURVEY, stat: '62%', text: 'Google a health claim first when they wonder if it’s true.' },
  { kicker: SURVEY, stat: '39 of 58', text: 'said they can’t tell which sources to trust.' },
  { kicker: SURVEY, stat: '47%', text: 'changed a diet, supplement or routine in the last year because of something they saw online.' },
  { kicker: SURVEY, stat: '64%', text: 'said a cited study or a source link they can open makes them believe a claim.' },
  { kicker: SURVEY, stat: '84%', text: 'see health claims on social media.' },
  { kicker: SURVEY, stat: '60%', text: 'said too many conflicting answers makes checking hard.' },
  { kicker: SURVEY, stat: '2 in 3', text: 'AI users double-check what it tells them, often or always.' },
  { kicker: SURVEY, text: 'Doctors were the most trusted source. AI chatbots scored lower than Google.' },
  // Facts
  { kicker: FUN, text: 'In 1747, James Lind tested six scurvy treatments on sailors. Citrus won. It’s often called one of the first controlled clinical trials.' },
  { kicker: FUN, text: 'The 1948 streptomycin trial for tuberculosis is often called the first properly randomized clinical trial.' },
  { kicker: FUN, text: 'Ice cream sales and sunburns rise together every summer. Correlation isn’t causation.' },
  { kicker: FUN, text: 'PubMed holds tens of millions of citations. We only read the ones that match your claim.' },
  { kicker: FUN, text: 'Trials assign a treatment. Observational studies just watch what happens. Both can be done well, and both can be done badly.' },
  { kicker: FUN, text: 'Study type describes how research was done, not how good it is.' },
  { kicker: FUN, text: 'Abstracts are short summaries. The full paper is where the details, and the caveats, live.' },
  { kicker: FUN, text: 'A single study is a clue, not a verdict.' },
  // Jokes
  { kicker: DOC, text: 'You know you should just ask your doctor, right?' },
  { kicker: DOC, text: 'This is why we don’t believe everything we see online.' },
  { kicker: DOC, text: 'Your group chat is not a peer-reviewed journal.' },
  { kicker: DOC, text: '“I read it on the internet” is not a citation.' },
  { kicker: DOC, text: 'Googling your symptoms is not a medical degree.' },
  { kicker: DOC, text: 'We’re a website. Please don’t make us diagnose your headache.' },
  { kicker: DOC, text: 'Not medical advice. Just homework, with citations.' },
]

function shuffled<T>(items: T[]): T[] {
  const copy = [...items]
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy
}

/** Index that steps through a list on a timer. */
function useCycle(length: number, ms: number) {
  const [index, setIndex] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setIndex(i => (i + 1) % length), ms)
    return () => window.clearInterval(id)
  }, [length, ms])
  return index
}

/** Shown while a claim is being checked: a silly status word, and a tip (survey number, fact or joke). */
export default function LoadingTips() {
  const verbs = useMemo(() => shuffled(VERBS), [])
  const tips = useMemo(() => shuffled(TIPS), [])
  const verb = verbs[useCycle(verbs.length, 2400)]
  const tip = tips[useCycle(tips.length, 6500)]

  // Purely decorative: hidden from screen readers so the live region doesn't re-announce every change.
  return (
    <div className="loading-tips" aria-hidden="true">
      <p className="search__status-sub loading-tips__verb" key={verb}>{verb}…</p>
      <div className="loading-tips__tip" key={tip.text}>
        <span className="search__kicker">{tip.kicker}</span>
        <p>
          {tip.stat && <strong className="loading-tips__stat">{tip.stat}</strong>}
          {tip.text}
        </p>
      </div>
    </div>
  )
}