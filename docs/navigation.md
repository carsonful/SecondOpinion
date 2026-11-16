# Page navigation

Issue: [#81](https://github.com/carsonful/SecondOpinion/issues/81).

## Addresses and titles

| Address | Page title |
| --- | --- |
| `/` | Second Opinion \| Research health claims |
| `/how-it-works` | How it works \| Second Opinion |
| `/about` | About \| Second Opinion |

The address selects the initial page, including after refresh. Trailing slashes
and query strings do not change which page is selected. Unknown paths show a
Page not found view with a home link. Its HTTP status is controlled by the host.

Navigation uses the browser History API. These three routes do not require a
new runtime dependency. `routes.tsx` contains the address and title mapping;
`usePageNavigation.ts` subscribes to `popstate` and adds history entries for
navigation within the app. Clicking the current address does not add a duplicate
history entry. Browser Back and Forward render the page named by the URL.

The brand, How it works, and About controls are real links. Ordinary clicks use
client navigation. Modified clicks, middle clicks, download links, and links
with another target retain browser behavior, including opening another tab.

## Focus, scrolling, and state

Each page renders inside one `main` landmark with the ID `main-content`. The
Skip to content link becomes visible on focus and moves focus to that landmark.
After page navigation, the app updates the document title, focuses the page's
main heading, and scrolls to the top. Heading focus does not add the heading to
the ordinary Tab sequence. Initial entry preserves normal browser focus and
fragment handling, so the first Tab reaches the skip link. Theme changes do not
trigger page navigation.

The claim checker stays mounted above the page switch. Browser history retains
its in-memory draft and results. Selecting the brand or the How it works call
to action explicitly returns Home and clears the draft and results, matching
the previous Home behavior. The search scope selection is retained. A full
refresh starts a new app instance; claims are not persisted in the URL or browser
storage. Existing in-flight request guards remain in the claim checker.

## Hosting

The static host must serve the built `index.html` for direct requests to the
three page addresses. Vite development and production preview do this locally.
For the production reference configuration, see the deployment work in
[#78](https://github.com/carsonful/SecondOpinion/issues/78). A host that returns
404 for `/about` before loading the application cannot support direct links.
Preserve real API errors and missing-asset 404 responses rather than sending
them to the SPA fallback. This implementation is mounted at the origin root.

## Repeatable browser checks

From `frontend`:

```sh
npm ci
npm run typecheck:e2e
npx playwright install chromium
npm run test:e2e
```

The test runner builds the app and starts Vite preview at `127.0.0.1:4173`.
`PLAYWRIGHT_PORT` selects another port. `PLAYWRIGHT_BASE_URL` uses an existing
test server and skips server startup. `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` can
select an installed Chromium binary. Test only a local or dedicated test app.

The navigation suite intercepts API requests, so it needs no Azure credentials,
PubMed access, or database. It checks direct loads, refresh, titles, link targets,
Back and Forward, focus, scrolling, keyboard activation, the skip link, modified
clicks, search state, public errors, query strings, unknown paths, and mobile
navigation. `npm run test:e2e:report` opens the generated HTML report. Screenshots
and traces are saved for failures and excluded from Git.

These browser checks test observable focus and accessible names. They are not
a claim that every screen reader has been manually tested. The wider contrast,
educational tabs, and assistive-technology checks belong to #85.

## Pending footer integration

The footer in [PR 87](https://github.com/carsonful/SecondOpinion/pull/87) was still
open when this branch was prepared. Its App callbacks use the previous `setPage`
function. When combining the changes, retain this branch's routed App, import
`Footer`, and place it immediately after `</main>`:

```tsx
<Footer
  onHowItWorks={() => navigate('how-it-works')}
  onAbout={() => navigate('about')}
/>
```

Keep the footer outside the main landmark and preserve PR 87's home disclaimer
and styles. The primary navigation tests use its explicit accessible name, so
the separately named footer navigation does not make their selectors ambiguous.
Run the full browser suite on the combined revision before merging.

## AI assistance

ChatGPT assisted with the routing code, browser tests, and this document. The
three commits use the `[ai-assisted]` tag. This change does not add model calls
or alter study retrieval, evidence interpretation, or scoring.
