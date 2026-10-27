# SecondOpinion

Find research behind health claims.

The app normalizes a health claim, searches PubMed, and displays related studies
with study-type labels, abstracts, and PMC full-text access status. Live search
does not assign evidence grades, confidence scores, or verdicts.

Three saved examples show curated verdicts. They load from PostgreSQL without
calling Azure or PubMed.

## Local setup

### Backend

Requires Python 3.11+.

```sh
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

The API runs at http://localhost:8000. Interactive API docs are at `/docs`,
the schema is at `/openapi.json`, and the health check is at `/api/health`.

Copy `backend/.env.example` to `backend/.env` and configure the services you use:

| Setting | Purpose |
| --- | --- |
| `AZURE_INFERENCE_ENDPOINT` | Resource base URL or `/openai/v1` URL for claim normalization. Project URLs ending in `/api/projects/...` are unsupported. |
| `AZURE_MODEL_DEPLOYMENT_NAME` | Exact Azure deployment name; it can differ from the model name. |
| `AZURE_INFERENCE_API_KEY` | Key for the resource serving that deployment. |
| `DATABASE_URL` | PostgreSQL connection string for saved examples. Startup creates and seeds `example_results` when configured. |
| `CACHE_DATABASE_URL` | Optional separate PostgreSQL database for claim results shared across processes and restarts. Must use a different database name from `DATABASE_URL`. |
| `NCBI_API_KEY` | Optional; raises the shared NCBI rate limit from 3 to 10 requests per second. |
| `NCBI_EMAIL` | Contact email for NCBI requests. |
| `CROSSREF_MAILTO` | Optional contact email for Crossref's polite pool. |
| `CORS_ORIGINS` | Allowed frontend origins as a JSON array; defaults to `["http://localhost:5173"]`. |

Uncached claim normalization requires the three Azure settings. PostgreSQL is
optional for claim search.
Restart the backend after changing settings. See `.env.example` for cache options.

### Frontend

```sh
cd frontend
npm install
npm run dev
```

The frontend runs at http://localhost:5173. Vite proxies `/api` to port 8000.
For hosting, route `/api` to the backend and add the frontend origin to
`CORS_ORIGINS`.

### Checks

From `backend/`, with the virtual environment activated:

```sh
pytest
```

From `frontend/`:

```sh
npm run build
```

Backend tests use recorded or mocked service responses. The PostgreSQL
integration tests require `TEST_DATABASE_URL` (examples) or
`TEST_CACHE_DATABASE_URL` (claim cache).

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Status and API version. |
| POST | `/api/claims` | Normalize a claim and retrieve deduplicated PubMed studies with PMC access status. |
| POST | `/api/claims/normalize` | Normalize a claim without searching. |
| GET | `/api/pubmed/search?q=...&limit=20` | Search PubMed in relevance order. |
| GET | `/api/pubmed/articles/{pmid}` | Retrieve one PubMed record. |
| GET | `/api/crossref/notices?doi=...` | Look up retractions, corrections, and expressions of concern separately from claim search. |
| GET | `/api/examples/{slug}` | Load `raw-milk`, `cold-showers`, or `cracking-knuckles`. |

For claim request/response fields, errors, retrieval limits, and caching, see
[the claim search contract](docs/claims-api.md). Repeated claims use an in-memory
cache; `?refresh=true` requests fresh results. Set `CACHE_DATABASE_URL` to enable
the optional shared PostgreSQL cache. From `backend/`, use
`python -m app.cache_admin put /path/to/claim-result.json --limit 20` to load a
complete result manually. The API guide covers validation, cache commands, TTLs,
and fallback behavior when the cache database is unavailable.

Crossref distinguishes an unchecked DOI (`retracted: null`) from a checked DOI
with no retraction found (`retracted: false`). Neither establishes study quality.

## Code map

The backend uses FastAPI and Pydantic:

- `backend/app/main.py`: app setup, shared service clients, and middleware.
- `backend/app/routers/`: HTTP endpoints.
- `backend/app/models/`: request and response schemas.
- `backend/app/services/`: normalization, source clients, metadata, and caching.
- `backend/app/data/example_results.json`: curated saved examples.
- `backend/tests/`: public test suite and recorded responses.

The frontend uses React 18, TypeScript, Vite, and plain CSS:

- `frontend/src/App.tsx`: page selection using React state.
- `frontend/src/components/SearchScreen.tsx` and `result/`: search and results.
- `frontend/src/hooks/useClaimChecker.ts`: claim requests and request state.
- `frontend/src/data/exampleClaims.ts` and `hydrateExample.tsx`: saved example links and rendering.
- `frontend/src/components/HowItWorksPage.tsx` and `how/`: educational demos, including a planned integrity-screening preview.
- `frontend/src/components/AboutPage.tsx` and `data/team.ts`: project and team content. Optional photos in `src/assets/team/` replace initials automatically.
- `frontend/src/styles/theme.css`: theme tokens and shared glass styles. `useTheme.ts` saves the selected theme; dark is the default.

Fonts load from Google Fonts in `frontend/index.html`. Search results and the
team section use light backgrounds in both themes.

## Current limits and future work

Study-type letters and colors identify research designs; they are not quality
grades. See [the study-type key](docs/study-guide.md).

Evidence appraisal, findings synthesis, automatic integrity screening in claim
search, and live verdict generation remain future work. Internal scoring and
integrity prototypes are retained in `evidence_workflow.py`, `evidence_models.py`,
`services/weighting.py`, and `services/integrity.py`; the claims endpoint does not
call them. Their proposed rules are in [the future grading plan](docs/evidence-grading.md).

Metadata extraction still needs independent validation. Other open work includes
deployment, accessibility review, and usability testing.
