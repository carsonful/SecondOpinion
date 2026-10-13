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

**Backend integration status:** `POST /api/claims` doesn't exist yet, so `useClaimChecker.ts` mocks one claim ("Is raw milk better for you than pasteurized?") from `src/data/mockResults.tsx`. Its explanation and further-reading tabs link to real, hand-checked sources (CDC, FDA, and a 2011 systematic review on PubMed). Any other claim hits the real fetch and shows the error state, which is expected for now. When the endpoint exists, drop the `MOCK_RESULTS` check and return the `VerdictData` shape from `src/types.ts`, including `sources` (title, publisher, category, takeaway, url, site): each source becomes one further-reading tab.

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
    mockResults.tsx       temporary mock verdict data (see above)
    team.ts               names, roles and blurbs for the About page
  hooks/
    useClaimChecker.ts    shared state + fetch logic for checking a claim
    useTheme.ts           light/dark mode, remembered per browser
  styles/
    theme.css             tokens for both themes, gradients, glass classes
  types.ts                shared types (VerdictData, Source)
  App.tsx                 page switching + top-level layout
```

**Recent changes (Oct 13):**
- Light/dark mode with a capsule toggle; dark mode is now "ink & cream"
- Gradients rebuilt on the Figma prototype's exact angle and stop positions
- Liquid-glass styling across the site, driven by theme tokens
- New "doctor's handwriting" accent font (Homemade Apple) replaces Arizonia
- Search and result merged into one page, with the result under the search
- Further reading shown as tabbed referral sheets with real source links
- Confidence-score "?" tooltip that works on hover, keyboard focus and tap
- How it works rebuilt as lab clipboards on a capsule tube, demos kept interactive
- About page built out: Rx pad, team capsules with photos, advisor, GitHub link
- `ResultScreen` and `FeatureCards` removed (replaced by the above); emojis removed

**Known gaps:**
- Real `/api/claims` endpoint (#22), returning `sources` for further reading
- Decide on the confidence score with the team: the result shows a percentage, but `docs/evidence-grading.md` says to avoid confidence percentages
- Accessibility pass (#28) and usability testing (#27)
- Router for shareable page links