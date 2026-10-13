import { ADVISOR, REPO_URL, STUDENTS, TeamMember } from '../data/team'
import './AboutPage.css'

// Picks up any photos in src/assets/team/ without breaking the build when
// some (or all) of them haven't been added yet.
const photoFiles = import.meta.glob<string>('../assets/team/*.{jpg,jpeg,png,webp}', {
  eager: true,
  import: 'default',
})

function photoFor(key: string): string | undefined {
  const match = Object.entries(photoFiles).find(([path]) => {
    const file = path.split('/').pop() ?? ''
    return file.replace(/\.[^.]+$/, '').toLowerCase() === key.toLowerCase()
  })
  return match?.[1]
}

function Avatar({ member }: { member: TeamMember }) {
  const src = photoFor(member.photo)
  return (
    <div className="about__avatar">
      {src ? <img src={src} alt={member.name} /> : <span aria-label={member.name}>{member.initials}</span>}
    </div>
  )
}

const VERDICTS = [
  { label: 'Supported', tag: 'Backed by science', tone: 'supported' },
  { label: 'Refuted', tag: 'Busted myth', tone: 'refuted' },
  { label: 'Unverified', tag: 'Little to no evidence', tone: 'unverified' },
]

function GitHubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9 19c-4 1.5-4-2-6-2.5m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12 12 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** The paper prescription pad next to the headline. Same in both themes. */
function RxPad() {
  return (
    <div className="rx" aria-label="What Second Opinion does, written as a prescription">
      <div className="rx__head">
        <span className="rx__brand">SECOND OPINION</span>
        <span className="rx__est">Est. 2026 · Gainesville, FL</span>
      </div>
      <div className="rx__body">
        <div className="rx__row">
          <span className="rx__symbol" aria-hidden="true">
            ℞
          </span>
          <div className="rx__lines">
            <span>
              <strong>For:</strong> any health claim you’re unsure about
            </span>
            <span>
              <strong>Directions:</strong> paste it in, read the verdict, click the sources
            </span>
            <span>
              <strong>Contains:</strong> graded studies, retraction checks, plain language
            </span>
            <span>
              <strong>Refills:</strong> unlimited
            </span>
          </div>
        </div>
        <div className="rx__sign">
          <span className="rx__signature">The Mythbusters</span>
          <span className="rx__line" />
          <span className="rx__caption">PRESCRIBED BY</span>
        </div>
      </div>
    </div>
  )
}

/** Brushed-foil blister strip holding the three verdict pills. */
function BlisterStrip() {
  return (
    <div className="blister" aria-label="The three possible verdicts">
      <span className="blister__title">THREE VERDICTS · ONE PER CLAIM</span>
      <div className="blister__row">
        {VERDICTS.map((v) => (
          <div key={v.label} className="blister__cell">
            <div className="blister__pocket">
              <div className={`blister__pill blister__pill--${v.tone}`}>
                <span className="blister__pill-gloss" aria-hidden="true" />
              </div>
            </div>
            <strong>{v.label}</strong>
            <span>{v.tag}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function AboutPage() {
  return (
    <div className="about-wrap">
      {/* Top: hero + project. Follows the theme (ink & cream in dark mode). */}
      <div className="about__top">
        <span className="about__float about__float--a glass-card" aria-hidden="true">
          <span className="about__float-half about__float-half--cream" />
        </span>

        <div className="about">
          <header className="about__hero">
            <div className="about__intro">
              <p className="about__eyebrow glass-pill">Senior Project · University of Florida</p>
              <h1 className="about__headline">
                Meet the
                <br />
                <span className="about__hand">Mythbusters</span>
              </h1>
              <p className="about__lede">
                Second Opinion started as a senior project at the Herbert Wertheim College of Engineering. We
                wanted something better than scrolling through search results to figure out whether a health
                claim holds up.
              </p>
            </div>
            <RxPad />
          </header>

          <section className="about__project glass-card" aria-labelledby="project-title">
            <div className="about__project-copy">
              <h2 id="project-title">The project</h2>
              <p>
                Paste any health claim and get a clear verdict, explained in plain language, with every source
                linked. We grade the studies behind the claim, check for retractions, and tell you when the
                evidence isn’t there.
              </p>
              <a className="about__repo" href={REPO_URL} target="_blank" rel="noreferrer">
                <GitHubIcon />
                View the code on GitHub
              </a>
            </div>
            <BlisterStrip />
          </section>
        </div>
      </div>

      {/* Team: always light, even in dark mode. */}
      <div className="about__bottom theme-light">
        <span className="about__float about__float--b glass-card" aria-hidden="true">
          <span className="about__float-half about__float-half--blue" />
        </span>

        <section className="about about__team" aria-labelledby="team-title">
          <h2 id="team-title" className="about__section-title">
            The team
          </h2>
          <div className="about__grid">
            {STUDENTS.map((m, i) => (
              <article key={m.name} className="about__capsule glass-card">
                <div className="about__capsule-top">
                  <Avatar member={m} />
                  <h3>{m.name}</h3>
                  <span className="about__role">{m.shortRole}</span>
                </div>
                <div className="about__seam" />
                <div className={`about__capsule-bottom about__tint--${i % 2 === 0 ? 'blue' : 'cream'}`}>
                  <p>{m.blurb}</p>
                </div>
                <span className="about__gloss" aria-hidden="true" />
              </article>
            ))}
          </div>

          <article className="about__advisor glass-card">
            <div className="about__advisor-left">
              <Avatar member={ADVISOR} />
              <div>
                <span className="about__role">{ADVISOR.role}</span>
                <h3>{ADVISOR.name}</h3>
              </div>
            </div>
            <div className="about__seam about__seam--vertical" />
            <div className="about__advisor-right about__tint--blue">
              <span className="about__advisor-title">{ADVISOR.title}</span>
              <p>{ADVISOR.blurb}</p>
            </div>
          </article>
        </section>
      </div>
    </div>
  )
}