# SecondOpinion
Busting health myths backed by science.

## Project structure

- `frontend/` — React + TypeScript (Vite)
- `backend/` — Python API (FastAPI)

## Getting started

### Backend

Requires Python 3.11+.

```
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Runs on http://localhost:8000. Health check at `/api/health`. API docs at `/docs`.

Credentials and optional settings go in `backend/.env` (see `backend/.env.example`).

Azure model inference uses these settings:

- `AZURE_INFERENCE_ENDPOINT`: the resource base URL or its `/openai/v1` URL. A project URL ending in `/api/projects/...` is not supported.
- `AZURE_MODEL_DEPLOYMENT_NAME`: the exact deployment name assigned in Azure, which may differ from the underlying model name.
- `AZURE_INFERENCE_API_KEY`: the API key for the resource serving that deployment.

These replace `AZURE_FOUNDRY_ENDPOINT`, `AZURE_FOUNDRY_DEPLOYMENT`, and
`AZURE_FOUNDRY_API_KEY`, respectively. Update existing environment variables to
the new names and restart the backend after changing them.

Saved demo results require PostgreSQL. Set `DATABASE_URL` in `backend/.env` to a
PostgreSQL connection string. Backend startup creates the `example_results` table
and inserts the three examples automatically. The saved verdicts and confidence
scores are curated demo content. They do not come from the unfinished live
evidence-grading pipeline. Loading an example does not call Azure Foundry or PubMed.

To run the tests:

```
cd backend
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pytest
```

Backend layout:

```
backend/app/
  main.py       # app factory, middleware, router registration
  config.py     # settings loaded from env / .env
  routers/      # HTTP endpoints (thin, delegate to services)
  models/       # pydantic schemas
  services/     # source API clients, normalization, grading
backend/tests/  # pytest suite
```

Endpoints (full schemas at `/docs`):

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Status and API version |
| POST | `/api/claims` | Normalize a health claim and retrieve deduplicated candidate studies with integrity notices |
| POST | `/api/claims/normalize` | Normalize one health claim into structured retrieval fields without searching |
| GET | `/api/pubmed/search?q=...&limit=20` | Search PubMed, returns full study records in relevance order |
| GET | `/api/pubmed/articles/{pmid}` | One PubMed record by PMID, 404 if it does not exist |
| GET | `/api/crossref/notices?doi=...` | Retractions, corrections, and expressions of concern for a paper, each with a link to the notice |
| GET | `/api/examples/{slug}` | PostgreSQL result for `raw-milk`, `cold-showers`, or `cracking-knuckles` |

PubMed calls are rate limited to stay under NCBI's ceiling (3 requests/second, or 10 with `NCBI_API_KEY` set) and retried on throttling or outages. If PubMed stays down the API returns 503. Crossref calls work the same way (set `CROSSREF_MAILTO` for the faster "polite" pool).

Crossref notices come from both publishers and the Retraction Watch database. A report's `retracted` flag is `None` when Crossref has no record of the DOI (unchecked) and `False` when it was checked and no notice was found, which is not the same as verified trustworthy. Tests run against recorded responses in `backend/tests/fixtures/`, so they never hit the live API.

`POST /api/claims` accepts `{"claim":"Does zinc cure colds?","limit":20}`.
The frontend handoff contract and hosting requirements are in
[`docs/claims-api.md`](docs/claims-api.md). Repeated claims are served from an
in-memory cache (add `?refresh=true` to skip it); see the caching section there.
The claim must contain 1–2,000 characters; the optional limit is 1–100.
Azure Foundry credentials are required for normalization. PostgreSQL is not
required for this retrieval endpoint. The response has `status: "candidates"`,
the submitted `claim`, `normalized` retrieval fields, `query_translation`,
PubMed's `total_results` (before deduplication), and `candidates`. Each candidate
contains `article`, `integrity` (`status` and `notices`), extracted `metadata`,
and provisional `weight` with a base design weight and its rationale. Candidates remain
in PubMed relevance order, including retracted and withheld papers for display.
Missing/invalid DOIs are unchecked. These are search candidates with provisional
design weights, not assessed findings or verdicts.

An empty search returns 200 with an empty candidates list. Invalid/non-health
input returns 422; unavailable normalization or evidence services return 503;
unusable evidence-source responses return 502. Crossref failures fail the request
rather than presenting an incomplete check as successful. Full request and
response schemas are available at `/docs`.

Every study passes through the integrity gate (`app/services/integrity.py`) before it can reach a verdict. Retracted studies (per Crossref or PubMed) are excluded and studies with an unresolved expression of concern are withheld, both with an effective weight of 0. Corrected studies stay in without a deduction, following `docs/evidence-grading.md`. Blocked studies are still returned for the evidence table with their notice links. `generate_verdict` only accepts `GateResult.admitted`, and there is no setting to turn the exclusion off.

Base study-design weights (#17) are implemented in
`app/services/weighting.py`, using versioned configuration in
`app/data/base_weights_v0.1.json`. `evidence_workflow.score_study()` records a
base weight and its rationale from an already resolved design; final contributions
await claim assessment. Unknown designs retain `null` weights. See
[`docs/evidence-grading.md`](docs/evidence-grading.md) for the design identifiers,
synthesis rules, and evidence-hierarchy references. The claim retrieval endpoint
extracts study designs and conservative participant counts (#14) and returns
base weights for display in an expandable, sortable evidence table (#26).
The 20-study independent extraction review remains pending; see the grading doc.

### Frontend

```
cd frontend
npm install
npm run dev
```

Runs on http://localhost:5173 and proxies `/api` requests to the backend.

**Tech:** React 18 + TypeScript, Vite, plain CSS (no framework). Design tokens live in `src/styles/theme.css`. Fonts are Comfortaa (body/UI, weights 500–700) and Homemade Apple (the "doctor's handwriting": the "Second" in the logo, "Mythbusters" on About, and handwritten notes), loaded via Google Fonts in `index.html`.

**Design system:**
- **Light and dark mode.** A sun/moon capsule toggle in the nav bar switches themes. The choice is saved in `localStorage` (`useTheme.ts`); dark is the default.
- **Gradients.** Both themes use the Figma gradient's angle and stops (114deg, 0 / 19 / 43 / 69 / 88 / 100%). Light mode runs sky blue to cream; dark mode ("ink & cream") is near-black navy with the Figma blue (#125FC9) as soft corner glows. The gradient is pinned to the viewport.
- **Liquid glass.** `.glass-card`, `.glass-pill` and `.glass-panel` read semantic tokens (`--card-bg`, `--text-strong`, …) defined per theme in `theme.css`, so components never hard-code theme colours.
- **Dark top, light bottom.** In dark mode, the Search and About pages keep their lower half light (the result area and the team). Those sections set their own light tokens in their CSS, so they stay readable in dark mode no matter what.
- **Props.** The paper Rx pad, the lab-report clipboards, the foil blister strips and the ink stamps look the same in both themes.

**Pages:**

| Screen | Component | Notes |
|---|---|---|
| Search + result (home) | `SearchScreen.tsx`, `result/` | Capsule search bar and example claims. Before a search: the three checks in a foil blister strip. After a search the result appears underneath on the same page: verdict capsule with confidence meter and a "?" tooltip (hover, focus or tap) explaining the score; chat-style explanation with sources linked inline; "Further reading" as tabbed referral sheets on a clipboard, one tab per source, each linking to the original; related claims; a not-medical-advice note. Loading and error states show in the same spot. |
| How it works | `HowItWorksPage.tsx`, `how/` | A capsule travels down a glass tube past three stations. Each station is a lab-report clipboard holding a working demo (normalize a messy claim, grade a study type, run a retraction scan); an ink stamp (NORMALIZED / GRADED / 1 RETRACTED) lands when you finish it. |
| About | `AboutPage.tsx` | Hero with a paper Rx pad, project capsule with the verdicts in a foil blister strip and a GitHub link, team as glass capsules with photos and roles, advisor capsule. Team info lives in `src/data/team.ts`; photos in `src/assets/team/` (`carson.jpg`, `nj.jpg`, …) are picked up automatically, with initials as a fallback. |

Navigation is React state in `App.tsx`, no router installed yet: the logo resets to search, nav links switch pages. `react-router-dom` is a quick follow-up if shareable links are needed.

**Backend integration status:** The three example claims fetch saved results through
`GET /api/examples/{slug}`. JSON explanation segments become React text and links
in the existing result display. Other claims use `POST /api/claims` and show
candidate studies, abstracts, and integrity notices in a separate results view.
These candidates include provisional base weights, metadata, and expandable
breakdowns, with sorting by base weight, year, or type. They have no computed
verdict or confidence score. Typing one of the
three exact example claims still retrieves its saved result.

Frontend layout:

```
frontend/src/
  assets/
    team/                team photos for the About page
  components/
    NavBar.tsx            logo, page links, theme toggle
    SearchScreen.tsx      search + result page (dark top, light bottom)
    result/
      VerdictResult.tsx   verdict capsule, explanation, related claims
      ScoreTip.tsx        the "?" tooltip next to the confidence score
      ReferralTabs.tsx    further reading: tabbed referral sheets
    HowItWorksPage.tsx    capsule tube + stations
    how/
      Clipboard.tsx       lab-report clipboard with an ink stamp
      NormalizeDemo.tsx   interactive demo: claim normalization
      GradingDemo.tsx     interactive demo: evidence grading
      RetractionDemo.tsx  interactive demo: retraction checks
    AboutPage.tsx         project, team and advisor
  data/
    exampleClaims.ts      labels and slugs for saved examples
    hydrateExample.tsx    renders JSON explanation segments as React content
    team.ts               names, roles and blurbs for the About page
  hooks/
    useClaimChecker.ts    shared state + fetch logic for checking a claim
    useTheme.ts           light/dark mode, remembered per browser
  styles/
    theme.css            design tokens, gradient, glass utility classes
  types.ts               shared TypeScript types
  App.tsx                page routing (state-based) + top-level layout
```

**Known gaps:** independent metadata extraction validation (#14), sample size and recency rules (#18), claim relevance and finding assessment, verdict generation (#20), explanation generation (#22), final effective scores in the evidence table (#26), expand How It Works content, About page content, accessibility pass (#28), usability testing (#27). The claim retrieval endpoint is implemented locally; deployment remains part of #16's acceptance criteria.
