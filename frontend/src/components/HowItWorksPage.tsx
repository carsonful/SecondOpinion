import FeatureCards from './FeatureCards'
import './HowItWorksPage.css'

export default function HowItWorksPage() {
  return (
    <section className="how">
      <h1 className="how__headline">How it works</h1>
      <p className="how__subhead">
        Three checks run on every claim before you see a verdict. More detail on each one is
        coming soon.
      </p>
      <FeatureCards />
    </section>
  )
}
