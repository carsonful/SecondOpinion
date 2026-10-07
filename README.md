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

**Tech:** React 18 + TypeScript, Vite, plain CSS (no framework — see `src/styles/theme.css` for design tokens). Fonts are Comfortaa (body/UI) and Arizonia (the "Second" script wordmark), loaded via Google Fonts in `index.html`.

**Design system:**
- Background is a navy-to-blue diagonal gradient with a radial highlight (`.page` in `theme.css`), matching the Figma prototype
- Three glassmorphism utility classes: `.glass-pill` (translucent, sits on the gradient — eyebrow badge, chips), `.glass-panel` (near-opaque frosted panel, readable dark text — verdict card, chat bubble, status messages), `.glass-card` (translucent dark card — feature cards)

**Pages:**

| Screen | Component | Notes |
|---|---|---|
| Search (home) | `SearchScreen.tsx` | Hero, claim input, example chips, loading/error states, feature cards below the fold |
| Result | `ResultScreen.tsx` | Verdict card (status, confidence score w/ tooltip) + chatbot-style explanation with sources linked inline, compact search bar to check another claim, related-claims chips |
| How it works | `HowItWorksPage.tsx` | Reuses the 3 feature cards; content to be expanded |
| About | `AboutPage.tsx` | Placeholder |

Navigation is React state in `App.tsx`, no router installed yet — logo/wordmark click resets to search, nav links switch pages. No real URLs change per page yet; `react-router-dom` is a quick follow-up if shareable links are needed later.

**Backend integration status:** `POST /api/claims` doesn't exist yet, so `useClaimChecker.ts` mocks one claim ("Is raw milk better for you than pasteurized?") from `src/data/mockResults.tsx` to demo the full flow. Any other claim hits the real fetch, gets a 404 from the missing endpoint, and correctly shows the app's error state — expected, not a bug. Once the real endpoint exists, drop the `MOCK_RESULTS` check in `useClaimChecker.ts` and make sure the response shape matches `VerdictData` in `src/types.ts`.

Frontend layout:

```
frontend/src/
  assets/              logo files
  components/
    NavBar.tsx          nav bar, logo/wordmark, page nav
    SearchScreen.tsx     home/search hero + examples + status states
    ResultScreen.tsx     verdict + chatbot explanation + related claims
    FeatureCards.tsx     claim normalization / evidence grading / retraction checks cards
    HowItWorksPage.tsx
    AboutPage.tsx
  data/
    mockResults.tsx      temporary mock verdict data (see above)
  hooks/
    useClaimChecker.ts   shared state + fetch logic for checking a claim
  styles/
    theme.css            design tokens, gradient, glass utility classes
  types.ts               shared TypeScript types
  App.tsx                page routing (state-based) + top-level layout
```

**Known gaps:** real `/api/claims` endpoint (#22), swap out mock data once it's live, expand How It Works content, About page content, accessibility pass (#28), usability testing (#27).
