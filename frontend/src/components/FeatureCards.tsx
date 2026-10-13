import './FeatureCards.css'

const FEATURES = [
  {
    title: 'Claim normalization',
    description: "Understands what you're actually asking, even from messy phrasing",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <rect x="4" y="8" width="16" height="12" rx="3" stroke="currentColor" strokeWidth="2" />
        <circle cx="9" cy="14" r="1.5" fill="currentColor" />
        <circle cx="15" cy="14" r="1.5" fill="currentColor" />
        <path d="M12 8V4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <circle cx="12" cy="3" r="1.3" fill="currentColor" />
      </svg>
    ),
  },
  {
    title: 'Evidence grading',
    description: 'Scores every study by type, sample size, and recency',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <rect x="4" y="12" width="4" height="8" rx="1" fill="currentColor" />
        <rect x="10" y="7" width="4" height="13" rx="1" fill="currentColor" />
        <rect x="16" y="4" width="4" height="16" rx="1" fill="currentColor" />
      </svg>
    ),
  },
  {
    title: 'Retraction checks',
    description: 'Automatically flags and excludes retracted or unreliable sources',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <path d="M6 3v18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M6 4h11l-3 4 3 4H6" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      </svg>
    ),
  },
]

export default function FeatureCards() {
  return (
    <div className="features">
      {FEATURES.map((f) => (
        <div key={f.title} className="features__card glass-card">
          <div className="features__icon">{f.icon}</div>
          <h3 className="features__title">{f.title}</h3>
          <p className="features__desc">{f.description}</p>
        </div>
      ))}
    </div>
  )
}
