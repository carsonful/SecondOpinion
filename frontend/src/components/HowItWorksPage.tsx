import { useCallback, useState } from 'react'
import Clipboard from './how/Clipboard'
import NormalizeDemo from './how/NormalizeDemo'
import GradingDemo from './how/GradingDemo'
import RetractionDemo from './how/RetractionDemo'
import './HowItWorksPage.css'

interface HowItWorksPageProps {
  onTryIt: () => void
}

export default function HowItWorksPage({ onTryIt }: HowItWorksPageProps) {
  // Each clipboard gets its stamp once its demo has been run
  const [normalized, setNormalized] = useState(false)
  const [graded, setGraded] = useState(false)
  const [screened, setScreened] = useState(false)
  const onNormalized = useCallback((d: boolean) => setNormalized(d), [])
  const onGraded = useCallback((d: boolean) => setGraded(d), [])
  const onScreened = useCallback((d: boolean) => setScreened(d), [])

  return (
    <div className="how">
      <header className="how__hero">
        <p className="how__eyebrow glass-pill">Three checks, every claim</p>
        <h1 className="how__headline">How it works</h1>
        <span className="how__hand how__hand--lead">every claim gets a full checkup</span>
        <p className="how__subhead">
          Your claim goes in the top, runs through three lab tests, and comes out the bottom as a verdict you can
          trust. Try each test yourself.
        </p>
      </header>

      {/* What goes in: the top of the tube */}
      <div className="how__capsule how__capsule--in">
        <div className="how__capsule-half how__capsule-half--glass glass-card">
          <span className="how__capsule-label">WHAT GOES IN</span>
          <span className="how__capsule-text">“my aunt swears raw milk is wayyy healthier than the store stuff??”</span>
        </div>
        <div className="how__capsule-seam" />
        <div className="how__capsule-half how__capsule-half--status">
          <span className="how__capsule-label">STATUS</span>
          <span className="how__hand">sent to the lab ↓</span>
        </div>
      </div>

      <section className="how__lab" aria-label="The three tests">
        <span className="how__tube glass-card" aria-hidden="true" />
        <span className="how__traveler" aria-hidden="true" />

        <div className="how__station">
          <div className="how__station-board">
            <Clipboard
              label="LAB REPORT · TEST 01"
              title="CLAIM INTAKE"
              stamp="NORMALIZED"
              tone="green"
              stamped={normalized}
              tilt={-1}
            >
              <NormalizeDemo onStatusChange={onNormalized} />
            </Clipboard>
          </div>
          <div className="how__node how__node--1" aria-hidden="true">
            1
          </div>
          <div className="how__station-info glass-card">
            <span className="how__hand">“what are you really asking?”</span>
            <h2>Claim normalization</h2>
            <p>
              People don’t type health claims like research questions. We pull out what’s being claimed, compared to
              what, and the effect, then write it up as one clear question to search.
            </p>
          </div>
        </div>

        <div className="how__station how__station--flip">
          <div className="how__station-board">
            <Clipboard
              label="LAB REPORT · TEST 02"
              title="EVIDENCE GRADING"
              stamp="GRADED"
              tone="blue"
              stamped={graded}
              tilt={1}
            >
              <GradingDemo onStatusChange={onGraded} />
            </Clipboard>
          </div>
          <div className="how__node how__node--2" aria-hidden="true">
            2
          </div>
          <div className="how__station-info glass-card">
            <span className="how__hand">“how good is the evidence?”</span>
            <h2>Evidence grading</h2>
            <p>
              Every study gets a category from how it was done, so a blog-cited case report can’t outweigh a trial.
              Animal studies and preprints are kept separate.
            </p>
          </div>
        </div>

        <div className="how__station">
          <div className="how__station-board">
            <Clipboard
              label="LAB REPORT · TEST 03"
              title="INTEGRITY SCREEN"
              stamp="1 RETRACTED"
              tone="red"
              stamped={screened}
              tilt={-0.8}
            >
              <RetractionDemo onStatusChange={onScreened} />
            </Clipboard>
          </div>
          <div className="how__node how__node--3" aria-hidden="true">
            3
          </div>
          <div className="how__station-info glass-card">
            <span className="how__hand">“can we still trust it?”</span>
            <h2>Retraction checks</h2>
            <p>
              Some viral claims trace back to papers that were later pulled. Every source is screened for retractions
              and integrity notices, and we show you the notice instead of hiding it.
            </p>
          </div>
        </div>
      </section>

      {/* What comes out: the bottom of the tube */}
      <div className="how__capsule how__capsule--out">
        <div className="how__capsule-half how__capsule-half--glass glass-card">
          <span className="how__capsule-label">WHAT COMES OUT</span>
          <span className="how__hand">results are in</span>
        </div>
        <div className="how__capsule-seam" />
        <div className="how__capsule-half how__capsule-half--verdict">
          <div>
            <strong>Refuted</strong>
            <span>Busted myth</span>
          </div>
          <button type="button" className="how__cta" onClick={onTryIt}>
            Check a claim →
          </button>
        </div>
      </div>
    </div>
  )
}