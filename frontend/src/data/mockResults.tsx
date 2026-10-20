import { VerdictData } from '../types'

// TEMP: standing in for the backend verdict endpoint (#22) until it exists.
// Every link below was checked by hand and says what the takeaway says.
const CDC_RAW_MILK = 'https://www.cdc.gov/food-safety/foods/raw-milk.html'
const FDA_RAW_MILK =
  'https://www.fda.gov/food/buy-store-serve-safe-food/raw-milk-misconceptions-and-danger-raw-milk-consumption'
const PASTEURIZATION_REVIEW = 'https://pubmed.ncbi.nlm.nih.gov/22054181/'

export const MOCK_RESULTS: Record<string, VerdictData> = {
  'is raw milk better for you than pasteurized?': {
    verdict: 'Refuted',
    tag: 'Busted myth',
    confidence: 86,
    chatBody: (
      <p>
        Short answer: no. Pasteurization kills harmful bacteria like <em>E. coli</em> and <em>Listeria</em>,
        and the{' '}
        <a href={CDC_RAW_MILK} target="_blank" rel="noreferrer">
          CDC
        </a>{' '}
        says pasteurized milk offers the same nutritional benefits without the risks. The{' '}
        <a href={FDA_RAW_MILK} target="_blank" rel="noreferrer">
          FDA
        </a>{' '}
        reaches the same conclusion, and a{' '}
        <a href={PASTEURIZATION_REVIEW} target="_blank" rel="noreferrer">
          2011 systematic review
        </a>{' '}
        found pasteurization has little effect on milk’s nutritional value.
      </p>
    ),
    sources: [
      {
        title: 'A systematic review and meta-analysis of the effects of pasteurization on milk vitamins',
        publisher: 'Journal of Food Protection · 2011',
        category: 'Research synthesis',
        takeaway: 'Pasteurization has little effect on milk’s nutritional value.',
        url: PASTEURIZATION_REVIEW,
        site: 'PubMed',
      },
      {
        title: 'Raw Milk Misconceptions and the Danger of Raw Milk Consumption',
        publisher: 'U.S. Food & Drug Administration',
        category: 'Public health guidance',
        takeaway: 'Raw milk is not nutritionally superior to pasteurized milk.',
        url: FDA_RAW_MILK,
        site: 'fda.gov',
      },
      {
        title: 'Raw Milk',
        publisher: 'Centers for Disease Control and Prevention',
        category: 'Public health guidance',
        takeaway: 'Pasteurized milk offers the same nutritional benefits without the risks.',
        url: CDC_RAW_MILK,
        site: 'cdc.gov',
      },
    ],
    relatedClaims: [
      'Does raw milk have more probiotics?',
      'Is organic milk healthier than regular milk?',
      'Do grass-fed cows produce better milk?',
    ],
  },
}