import { ADVISOR, INTERNS, REPO_URL, STUDENTS, SUPERVISOR, TeamMember } from '../data/team'
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

// The research poster. Lives next to the team photos; any common extension and case works
// (researchposter.JPG, researchposter.jpg, .png). Without the file the section still shows.
const posterFiles = import.meta.glob<string>('../assets/team/researchposter.{jpg,JPG,jpeg,JPEG,png,PNG,webp}', {
  eager: true,
  import: 'default',
})
const POSTER_SRC: string | undefined = Object.values(posterFiles)[0]

function Avatar({ member }: { member: TeamMember }) {
  const src = photoFor(member.photo)
  return (
    <div className="about__avatar">
      {src ? <img src={src} alt={member.name} /> : <span aria-label={member.name}>{member.initials}</span>}
    </div>
  )
}

/** Small headshot of the owner, pinned to the corner of their intern's avatar. */
function OwnerBadge({ member }: { member: TeamMember }) {
  const src = photoFor(member.photo)
  return (
    <span
      aria-hidden="true"
      style={{
        position: 'absolute',
        right: -6,
        bottom: -2,
        width: 46,
        height: 46,
        borderRadius: '50%',
        overflow: 'hidden',
        border: '3px solid rgba(255, 255, 255, 0.95)',
        boxShadow: '0 0 0 2px rgba(158, 204, 250, 0.9), 0 6px 14px rgba(11, 25, 87, 0.25)',
        background: 'linear-gradient(160deg, #FFF8EE, #DCEBFA)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 13,
        fontWeight: 700,
        color: '#1B3B6F',
      }}
    >
      {src ? <img src={src} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} /> : member.initials}
    </span>
  )
}

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
              <strong>Directions:</strong> paste it in, explore studies, open the sources
            </span>
            <span>
              <strong>Contains:</strong> relevance-sorted studies, a cited overview, PMC access
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

/** Where we're presenting. Sits under the project card. */
function ShowcaseCard() {
  return (
    <section
      className="glass-card"
      aria-labelledby="showcase-title"
      style={{
        marginTop: 40,
        padding: 'clamp(22px, 4vw, 36px)',
        borderRadius: 36,
        display: 'grid',
        gridTemplateColumns: POSTER_SRC ? 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))' : '1fr',
        gap: 'clamp(20px, 4vw, 40px)',
        alignItems: 'center',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'flex-start', minWidth: 0 }}>
        <p className="about__eyebrow glass-pill" style={{ margin: 0 }}>
          Fall 2026 Senior Design Showcase
        </p>
        <h2 id="showcase-title" style={{ margin: 0 }}>
          Come see us present
        </h2>
        <p style={{ margin: 0, lineHeight: 1.6, color: 'var(--text-body)' }}>
          We’re presenting Second Opinion at the Fall 2026 Senior Design Showcase on{' '}
          <strong style={{ color: 'var(--text-strong)' }}>Thursday, November 19th, 2026</strong>, at the University
          of Florida. Come find our poster and meet the Mythbusters.
        </p>
        <span
          className="glass-pill"
          style={{ display: 'inline-block', padding: '8px 16px', borderRadius: 999, fontSize: 13, fontWeight: 700, color: 'var(--accent-text)' }}
        >
          Thu · Nov 19, 2026 · University of Florida
        </span>
        <a className="about__repo" href={REPO_URL} target="_blank" rel="noreferrer">
          <GitHubIcon />
          View the code on GitHub
        </a>
      </div>

      {POSTER_SRC && (
        <a
          href={POSTER_SRC}
          target="_blank"
          rel="noreferrer"
          aria-label="Open our research poster full size"
          style={{ display: 'block', minWidth: 0, textDecoration: 'none' }}
        >
          <img
            src={POSTER_SRC}
            alt="Our Second Opinion research poster for the Fall 2026 Senior Design Showcase"
            style={{
              display: 'block',
              width: '100%',
              maxHeight: 460,
              objectFit: 'contain',
              borderRadius: 18,
              border: '1px solid rgba(255, 255, 255, 0.85)',
              boxShadow: '0 18px 40px rgba(11, 25, 87, 0.22)',
              background: '#fff',
            }}
          />
          <span style={{ display: 'block', marginTop: 10, textAlign: 'center', fontSize: 12.5, color: 'var(--text-muted)' }}>
            Our research poster · click to enlarge
          </span>
        </a>
      )}
    </section>
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

          <ShowcaseCard />
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

          <article className="about__advisor glass-card" style={{ marginTop: 20 }}>
            <div className="about__advisor-left">
              <Avatar member={SUPERVISOR} />
              <div>
                <span className="about__role">{SUPERVISOR.role}</span>
                <h3>{SUPERVISOR.name}</h3>
              </div>
            </div>
            <div className="about__seam about__seam--vertical" />
            <div className="about__advisor-right about__tint--cream">
              <span className="about__advisor-title">{SUPERVISOR.title}</span>
              <p>{SUPERVISOR.blurb}</p>
            </div>
          </article>

          <h2 className="about__section-title" style={{ marginTop: 40 }}>
            The interns
          </h2>
          <div className="about__grid">
            {INTERNS.map((m, i) => {
              const owner = STUDENTS.find((s) => s.name === m.owner)
              return (
                <article key={m.name} className="about__capsule glass-card" style={{ marginTop: 0 }}>
                  <div className="about__capsule-top">
                    <div style={{ position: 'relative' }}>
                      <Avatar member={m} />
                      {owner && <OwnerBadge member={owner} />}
                    </div>
                    <h3>{m.name}</h3>
                    <span className="about__role">{m.shortRole}</span>
                    {owner && (
                      <span
                        className="about__role"
                        style={{
                          marginTop: 4,
                          padding: '4px 12px',
                          borderRadius: 999,
                          background: 'rgba(255, 255, 255, 0.7)',
                          border: '1px solid rgba(255, 255, 255, 0.95)',
                          color: '#5A6B8C',
                        }}
                      >
                        Reports to {owner.name.split(' ')[0]}
                      </span>
                    )}
                  </div>
                  <div className="about__seam" />
                  <div className={`about__capsule-bottom about__tint--${i % 2 === 0 ? 'blue' : 'cream'}`}>
                    <p>{m.blurb}</p>
                  </div>
                  <span className="about__gloss" aria-hidden="true" />
                </article>
              )
            })}
          </div>
        </section>
      </div>
    </div>
  )
}