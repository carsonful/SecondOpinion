import { useState } from 'react'
import Clipboard from './how/Clipboard'
import NormalizeDemo from './how/NormalizeDemo'
import StudyTypeDemo from './how/StudyTypeDemo'
import RetractionDemo from './how/RetractionDemo'
import './HowItWorksPage.css'

interface HowItWorksPageProps {
  onTryIt: () => void
}

export default function HowItWorksPage({ onTryIt }: HowItWorksPageProps) {
  // Each clipboard gets its stamp once its demo has been run
  const [normalized, setNormalized] = useState(false)
  const [classified, setClassified] = useState(false)
  const [screened, setScreened] = useState(false)

  return (
    <div className="how">
      <header className="how__hero">
        <p className="how__eyebrow glass-pill">Explore the evidence</p>
        <h1 className="how__headline">How it works</h1>
        <span className="how__hand how__hand--lead">from a question to related studies</span>
        <p className="how__subhead">
          Claim search turns your question into a PubMed query and shows related studies, their designs, and
          available abstracts or PMC full text. Try the examples below, including a preview of planned integrity screening.
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
              <NormalizeDemo onStatusChange={setNormalized} />
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
              title="STUDY TYPE"
              stamp="CLASSIFIED"
              tone="blue"
              stamped={classified}
              tilt={1}
            >
              <StudyTypeDemo onStatusChange={setClassified} />
            </Clipboard>
          </div>
          <div className="how__node how__node--2" aria-hidden="true">
            2
          </div>
          <div className="how__station-info glass-card">
            <span className="how__hand">“what kind of study is this?”</span>
            <h2>Study types</h2>
            <p>
              Study labels describe the research design, such as a trial, review, or case report. They help you read
              the results, but do not establish study quality or whether the claim is true. The demo also illustrates publication flags.
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
              <RetractionDemo onStatusChange={setScreened} />
            </Clipboard>
          </div>
          <div className="how__node how__node--3" aria-hidden="true">
            3
          </div>
          <div className="how__station-info glass-card">
            <span className="how__hand">“can we still trust it?”</span>
            <h2>Retraction checks · preview</h2>
            <p>
              This sample shows how retractions, corrections, and concerns could be displayed. Crossref notice lookup
              is available separately; automatic integrity screening is planned for a future claim-search release.
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
            <strong>Related studies</strong>
            <span>Study types, abstracts, and access</span>
          </div>
          <button type="button" className="how__cta" onClick={onTryIt}>
            Check a claim →
          </button>
        </div>
      </div>
    </div>
  )
}
