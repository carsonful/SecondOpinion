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
| GET | `/api/pubmed/search?q=...&limit=20` | Search PubMed, returns full study records in relevance order |
| GET | `/api/pubmed/articles/{pmid}` | One PubMed record by PMID, 404 if it does not exist |
| GET | `/api/examples/{slug}` | PostgreSQL result for `raw-milk`, `cold-showers`, or `cracking-knuckles` |

PubMed calls are rate limited to stay under NCBI's ceiling (3 requests/second, or 10 with `NCBI_API_KEY` set) and retried on throttling or outages. If PubMed stays down the API returns 503. Tests run against recorded responses in `backend/tests/fixtures/`, so they never hit the live API.

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
in the existing result display. Manually entered claims continue to use
`POST /api/claims`; that endpoint does not exist yet, so other claims show the
existing error state. Typing one of the three exact example claims also retrieves
its saved result.

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

**Known gaps:** real `/api/claims` endpoint (#22), expand How It Works content, About page content, accessibility pass (#28), usability testing (#27).
