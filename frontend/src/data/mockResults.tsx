import { VerdictData } from '../types'

// TEMP: standing in for the backend verdict endpoint (#22) until it exists.
export const MOCK_RESULTS: Record<string, VerdictData> = {
  'is raw milk better for you than pasteurized?': {
    verdict: 'Refuted',
    tag: 'Busted myth',
    confidence: 86,
    chatBody: (
      <p>
        Short answer: no — pasteurization kills harmful bacteria like{' '}
        <em>E. coli</em> and <em>Listeria</em> without meaningfully changing the
        milk's nutrition. A{' '}
        <a href="#" target="_blank" rel="noreferrer">
          CDC food safety review
        </a>{' '}
        found no meaningful nutrient loss from pasteurization, and a{' '}
        <a href="#" target="_blank" rel="noreferrer">
          cohort study in the Journal of Dairy Science
        </a>{' '}
        backs that up. The "better nutrition" claim mostly traces back to a
        2019 blog post that's since been retracted — not an actual study.
      </p>
    ),
    relatedClaims: [
      'Does raw milk have more probiotics?',
      'Is organic milk healthier than regular milk?',
      'Do grass-fed cows produce better milk?',
    ],
  },
}
