import { VerdictData } from '../../types'
import ScoreTip from './ScoreTip'
import ReferralTabs from './ReferralTabs'

function verdictTone(verdict: string) {
  const v = verdict.toLowerCase()
  if (v.includes('refut') || v.includes('bust')) return 'refuted'
  if (v.includes('confirm') || v.includes('support')) return 'supported'
  return 'unverified'
}

const CAP_COLORS = [
  'linear-gradient(135deg,#3d8ed6,#2a6cb8)',
  'linear-gradient(135deg,#F6E4C8,#D6B482)',
  'linear-gradient(135deg,#1B3B6F,#0B1957)',
]

interface VerdictResultProps {
  verdict: VerdictData
  onPickRelated: (text: string) => void
  onHowItWorks?: () => void
}

/** The result, shown in the light half under the search. */
export default function VerdictResult({ verdict, onPickRelated, onHowItWorks }: VerdictResultProps) {
  const tone = verdictTone(verdict.verdict)
  const sources = verdict.sources ?? []
  const confidence = Math.max(0, Math.min(100, verdict.confidence))

  return (
    <div className="vr">
      <div className="vr__top">
        <span className="search__kicker">YOUR SECOND OPINION</span>
        <span className="search__hand">results are in</span>
      </div>

      <div className="vr__row">
        <div className={`vr__capsule vr__capsule--${tone}`}>
          <div className="vr__capsule-top">
            <span className="vr__tag">{verdict.tag}</span>
            <strong className="vr__label">{verdict.verdict}</strong>
          </div>
          <div className="vr__seam" />
          <div className="vr__capsule-bottom">
            <div className="vr__score">
              <span>{confidence} confidence score</span>
              <ScoreTip onHowItWorks={onHowItWorks} />
            </div>
            <div
              className="vr__meter"
              role="meter"
              aria-label="Confidence score"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={confidence}
            >
              <span style={{ width: `${confidence}%` }} />
            </div>
          </div>
        </div>

        <div className="vr__chat glass-card">
          <span className="vr__avatar" aria-hidden="true">
            SO
          </span>
          <div className="vr__chat-body">
            <div className="vr__chat-text">{verdict.chatBody}</div>
            {sources.length > 0 && (
              <div className="vr__chips">
                <span className="vr__chip">
                  {sources.length} {sources.length === 1 ? 'source' : 'sources'}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {sources.length > 0 && <ReferralTabs sources={sources} />}

      {verdict.relatedClaims && verdict.relatedClaims.length > 0 && (
        <div className="vr__related glass-card">
          <span className="vr__related-title">Related claims</span>
          {verdict.relatedClaims.map((text, i) => (
            <button key={text} type="button" className="search__chip" onClick={() => onPickRelated(text)}>
              <span>{text}</span>
              <span style={{ background: CAP_COLORS[i % CAP_COLORS.length] }} />
            </button>
          ))}
        </div>
      )}

      <p className="vr__fine">Second Opinion summarizes research. It isn’t medical advice.</p>
    </div>
  )
}