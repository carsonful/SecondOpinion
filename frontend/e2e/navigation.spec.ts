import { expect, test } from '@playwright/test'

const pages = [
  { path: '/', heading: /Is that health claim/, title: 'Second Opinion | Research health claims' },
  { path: '/how-it-works', heading: 'How it works', title: 'How it works | Second Opinion' },
  { path: '/about', heading: /Meet the/, title: 'About | Second Opinion' },
]

test.beforeEach(async ({ page }) => {
  // Every API call is intercepted. Navigation tests cannot consume provider credits.
  await page.route('**/api/**', route => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({ detail: 'Service unavailable for this offline test.' }),
  }))
})

for (const route of pages) {
  test(`direct load and refresh restore ${route.path}`, async ({ page }) => {
    await page.goto(route.path)
    await expect(page).toHaveTitle(route.title)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(route.heading)
    await expect(page.getByRole('main')).toHaveCount(1)
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
    await page.reload()
    await expect(page).toHaveTitle(route.title)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(route.heading)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })
}

test('links expose stable addresses and only the current route is marked', async ({ page }) => {
  await page.goto('/')
  const brand = page.getByRole('link', { name: 'Second Opinion home' })
  const how = page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'How it works' })
  const about = page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true })
  await expect(brand).toHaveAttribute('href', '/')
  await expect(how).toHaveAttribute('href', '/how-it-works')
  await expect(about).toHaveAttribute('href', '/about')
  await expect(brand).toHaveAttribute('aria-current', 'page')
  await how.click()
  await expect(page).toHaveURL(/\/how-it-works$/)
  await expect(how).toHaveAttribute('aria-current', 'page')
  await expect(brand).not.toHaveAttribute('aria-current')
  await about.click()
  await expect(page).toHaveURL(/\/about$/)
  await expect(about).toHaveAttribute('aria-current', 'page')
  await expect(how).not.toHaveAttribute('aria-current')
})

test('Back and Forward restore page, title and heading focus', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'How it works' }).click()
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true }).click()
  await page.goBack()
  await expect(page).toHaveURL(/\/how-it-works$/)
  await expect(page).toHaveTitle('How it works | Second Opinion')
  await expect(page.getByRole('heading', { name: 'How it works', exact: true })).toBeFocused()
  await page.goBack()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
  await page.goForward()
  await expect(page).toHaveURL(/\/how-it-works$/)
  await page.goForward()
  await expect(page).toHaveURL(/\/about$/)
  await expect(page).toHaveTitle('About | Second Opinion')
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
})

test('navigation resets scrolling without adding history for the same address', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true }).click()
  const historyLength = await page.evaluate(() => history.length)
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  // Use keyboard activation so Playwright does not first scroll the header into view.
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true })
    .evaluate(element => element.focus({ preventScroll: true }))
  expect(await page.evaluate(() => scrollY)).toBeGreaterThan(0)
  await page.keyboard.press('Enter')
  await expect.poll(() => page.evaluate(() => scrollY)).toBe(0)
  expect(await page.evaluate(() => history.length)).toBe(historyLength)
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
  await page.goBack()
  await expect(page).toHaveURL(/\/$/)
})

test('keyboard navigation activates links and moves focus into the next page', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'How it works' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'How it works', exact: true })).toBeFocused()
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
})

test('skip link is visible when focused and moves focus to the main landmark', async ({ page }) => {
  await page.goto('/')
  const skip = page.getByRole('link', { name: 'Skip to content' })
  await page.keyboard.press('Tab')
  await expect(skip).toBeFocused()
  const box = await skip.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.y).toBeGreaterThanOrEqual(0)
  await page.keyboard.press('Enter')
  await expect(page.getByRole('main')).toBeFocused()
  await expect(page).toHaveURL(/\/$/)
})

for (const modifier of ['ctrlKey', 'metaKey', 'shiftKey', 'altKey']) {
  test(`${modifier} click retains native link behavior`, async ({ page }) => {
    await page.goto('/')
    const intercepted = await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true }).evaluate((link, key) => {
      let prevented = false
      // Observe React's handler, then suppress browser side effects for this assertion.
      const observe = (event: MouseEvent) => {
        prevented = event.defaultPrevented
        event.preventDefault()
      }
      document.addEventListener('click', observe, { once: true })
      link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, [key]: true }))
      return prevented
    }, modifier)
    expect(intercepted).toBe(false)
    await expect(page).toHaveURL(/\/$/)
  })
}

test('middle click and explicit new-window targets are not intercepted', async ({ page }) => {
  await page.goto('/')
  const results = await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true }).evaluate(link => {
    const observeClick = (button: number) => {
      let prevented = false
      document.addEventListener('click', event => {
        prevented = event.defaultPrevented
        event.preventDefault()
      }, { once: true })
      link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, button }))
      return prevented
    }
    const middle = observeClick(1)
    link.setAttribute('target', '_blank')
    const blank = observeClick(0)
    link.removeAttribute('target')
    link.setAttribute('download', '')
    const download = observeClick(0)
    return [middle, blank, download]
  })
  expect(results).toEqual([false, false, false])
  await expect(page).toHaveURL(/\/$/)
})

test('browser history retains draft text while explicit Home resets it', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Health claim' }).fill('Does zinc shorten a cold?')
  await page.getByRole('switch', { name: 'PubMed Central only' }).uncheck()
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true }).click()
  await page.goBack()
  await expect(page.getByRole('textbox', { name: 'Health claim' })).toHaveValue('Does zinc shorten a cold?')
  await expect(page.getByRole('switch', { name: 'PubMed Central only' })).not.toBeChecked()
  await page.getByRole('link', { name: 'Second Opinion home' }).click()
  await expect(page.getByRole('textbox', { name: 'Health claim' })).toHaveValue('')
  await expect(page.getByRole('switch', { name: 'PubMed Central only' })).not.toBeChecked()
})

test('search and public errors still work after navigating between pages', async ({ page }) => {
  let requests = 0
  await page.route('**/api/claims', async route => {
    requests++
    expect(route.request().postDataJSON()).toEqual({ claim: 'Does zinc shorten a cold?', pmc_only: true })
    await route.fulfill({ status: 503, contentType: 'application/json', body: '{}' })
  })
  await page.goto('/how-it-works')
  await page.getByRole('link', { name: 'Second Opinion home' }).click()
  await page.getByRole('textbox', { name: 'Health claim' }).fill('Does zinc shorten a cold?')
  await page.getByRole('button', { name: 'Check claim', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('An evidence service is unavailable')
  expect(requests).toBe(1)
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true }).click()
  await page.goBack()
  await expect(page.getByRole('alert')).toContainText('An evidence service is unavailable')
  expect(requests).toBe(1)
})

test('a retrieved study survives Back without another claim request or result scroll', async ({ page }) => {
  let requests = 0
  await page.route('**/api/claims', async route => {
    requests++
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      status: 'candidates', claim: 'Recorded fixture claim', normalized: { query: 'fixture' },
      pmc_only: true, total_results: 1, cached: false,
      coverage: { retrieved_studies: 1, full_text_available: 0, abstract_only: 1, metadata_only: 0 },
      candidates: [{
        article: {
          pmid: '123456', title: 'Recorded study for navigation testing',
          abstract: 'A recorded response. No provider is contacted.',
          journal: 'Fixture journal', year: 2026, publication_types: [],
          url: 'https://pubmed.ncbi.nlm.nih.gov/123456/',
        },
        metadata: { design: 'cohort', population: 'human' },
        access: {
          level: 'abstract_only', reason: 'fixture', detail: '', pmc_id: null,
          source_url: null, license: null, sections: [],
        },
      }],
    }) })
  })
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Health claim' }).fill('Recorded fixture claim')
  await page.getByRole('button', { name: 'Check claim', exact: true }).click()
  await expect(page.getByRole('link', { name: /Recorded study for navigation testing/ })).toBeVisible()
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true }).click()
  await page.goBack()
  await expect(page.getByRole('link', { name: /Recorded study for navigation testing/ })).toBeVisible()
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
  await expect.poll(() => page.evaluate(() => scrollY)).toBe(0)
  expect(requests).toBe(1)
})

test('changing the theme does not move focus or create navigation history', async ({ page }) => {
  await page.goto('/about')
  const initialTitle = await page.title()
  const initialLength = await page.evaluate(() => history.length)
  const toggle = page.getByRole('button', { name: 'Switch to light mode' })
  await toggle.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Switch to dark mode' })).toBeFocused()
  await expect(page).toHaveTitle(initialTitle)
  expect(await page.evaluate(() => history.length)).toBe(initialLength)
})

test('query strings and a trailing slash still select the requested page', async ({ page }) => {
  await page.goto('/how-it-works/?source=shared#main-content')
  await expect(page).toHaveTitle('How it works | Second Opinion')
  await expect(page.getByRole('heading', { name: 'How it works', exact: true })).toBeVisible()
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'About', exact: true }).click()
  await page.goBack()
  await expect(page).toHaveURL(/\/how-it-works\/\?source=shared#main-content$/)
  await expect(page).toHaveTitle('How it works | Second Opinion')
})

test('unknown addresses show an explicit page with a working home link', async ({ page }) => {
  await page.goto('/this-page-does-not-exist')
  await expect(page).toHaveTitle('Page not found | Second Opinion')
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  await expect(page.locator('[aria-current="page"]')).toHaveCount(0)
  await page.getByRole('main').getByRole('link', { name: 'Go to the home page' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('textbox', { name: 'Health claim' })).toBeVisible()
})

test('mobile navigation keeps the same routes and focused headings', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  for (const name of ['How it works', 'About']) {
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name, exact: true }).click()
    await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  }
})
