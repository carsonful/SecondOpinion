# SecondOpinion

Find research behind health claims.

The app normalizes a health claim, searches PubMed, and displays related studies
with study-type labels, abstracts, and PMC full-text access status. The live results
page automatically requests a cited research overview of the retrieved abstracts,
with individual explanations, relevance coverage, and information gaps. Live search
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
optional for claim search. When the saved examples database is not configured or
cannot be reached, the backend still starts and the example buttons run a live
search instead.
Restart the backend after changing settings. See `.env.example` for cache options.

### Request limits and logging

The model-backed POST routes (`/api/claims`, `/api/claims/normalize`, and
`/api/claims/overview/{analysis_id}`) share a per-client token bucket: a burst of
10 requests, refilling at 10 requests per 60 seconds. All attempts count,
including cache hits, invalid requests, and provider failures. An overview's
internal model retries do not consume additional inbound tokens. A limited
request returns `429` and a `Retry-After` header in seconds before model work
starts. Configure the `INFERENCE_RATE_LIMIT_*` settings in `.env.example`;
tests can set `INFERENCE_RATE_LIMIT_ENABLED=false`.

Limits and client tracking are bounded and local to each process. Idle client
entries expire after one window; when tracking is full, new clients receive
`429` rather than evicting active limits. Restarting resets quotas. This is a
basic abuse control, not a global Azure spending cap or a concurrency limit.
Use one backend worker initially, and shared limits or an ingress gateway
before scaling across workers or instances.

Client identity uses the ASGI peer address; application code never trusts
`X-Forwarded-For` or `X-Real-IP` directly. Behind a reverse proxy, configure
Uvicorn's `--forwarded-allow-ips` with only the actual trusted proxy addresses
and prevent direct access around the proxy. Do not use `*` for an exposed
backend. Without trusted forwarding, visitors through one proxy share a quota.

Normalization application logs contain only success, error class, and provider;
they omit claim text, extracted fields, and search queries. Transient upstream
transport logs record exception classes instead of exception messages. Public
normalization failures use stable messages rather than provider/configuration
details. Hosting access logs, HTTP-client debug logs, and Azure telemetry are
separate: configure their retention and redaction before public deployment.

### Frontend

```sh
cd frontend
npm install
npm run dev
```

The frontend runs at http://localhost:5173. Vite proxies `/api` to port 8000.
For hosting, route `/api` to the backend and add the frontend origin to
`CORS_ORIGINS`.

To check the production build locally, run `npm run build` followed by
`npm run preview`. Preview serves the built app with the security policy in
`frontend/securityHeaders.ts` and proxies `/api` to port 8000. The development
server retains Vite's normal hot-reload behavior.

### Browser security policies

The API sends `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: strict-origin-when-cross-origin`, and a `Permissions-Policy`
disabling camera, microphone, location, payment, and USB access. JSON API paths
and `/openapi.json` receive a CSP denying subresources, framing, base URLs, and
form submissions. Swagger/ReDoc retain their normal asset loading and do not
receive the JSON-only CSP. HSTS is sent only when the ASGI connection scheme is
HTTPS; raw forwarding headers are not used to decide this.

CORS accepts only configured explicit HTTP(S) origins, GET/POST/OPTIONS, and
the Content-Type request header (plus standard CORS safelisted headers).
`Retry-After` remains readable by allowed frontends. CORS controls browser access
to API responses; it is not authentication or request-abuse prevention.

The production-preview frontend CSP permits scripts and fonts only from the
same origin, blocks framing, and permits API connections only to the same origin.
Inline styles remain allowed for React's dynamic colors and illustrations;
inline scripts are not allowed. The font files, subsets, and redistribution
licenses live in `frontend/public/fonts` and are copied into `dist/fonts`.

These policies are ready to test locally. Vite's preview headers are not baked
into `dist`: the eventual static host must serve the same headers. If the frontend
calls a separate API origin directly, add that exact origin to frontend CSP
`connect-src` and configure backend `CORS_ORIGINS` separately. HTTPS redirects,
trusted forwarding, static-host HSTS, and verification of host-generated error
responses remain deployment work. API policies also cover handled errors and
unexpected server errors generated by FastAPI.

### Checks

GitHub Actions runs backend tests and the frontend production build on pull
requests and pushes to `main`, alongside SonarQube. These two checks do not need
Azure credentials or database secrets; database integration tests remain skipped
without the corresponding test database URLs. The workflow is validation only
and does not deploy the app.

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

Fonts load from bundled WOFF2 files in `frontend/public/fonts`. Search results and the
team section use light backgrounds in both themes.

## Current limits and future work

Study-type letters and colors identify research designs; they are not quality
grades. See [the study-type key](docs/study-guide.md).

Formal evidence appraisal and live verdict generation remain future work.
Live search screens integrity notices and provides an abstract-based research
overview; it does not grade studies or establish whether a claim is true. Internal scoring and
integrity prototypes are retained in `evidence_workflow.py`, `evidence_models.py`,
`services/weighting.py`, and `services/integrity.py`; the claims endpoint does not
call them. Their proposed rules are in [the future grading plan](docs/evidence-grading.md).

Metadata extraction still needs independent validation. Other open work includes
deployment, accessibility review, and usability testing.

## Automatic research overview

Search returns an `analysis_id` for a trusted, immutable result snapshot. The results
page immediately displays papers and automatically calls
`POST /api/claims/overview/{analysis_id}`. Azure reads eligible abstracts (up to the
first 20 retained papers), then synthesizes the validated readings with PMID citations.
Retracted papers are excluded; corrections and expressions of concern are withheld
because their effect on findings has not been resolved. Unchecked records remain
explicitly labeled. Missing abstracts are not inferred from titles.

The model selects numbered source passages; the server inserts their original text
and checks that every overview citation identifies an analyzed paper. These checks establish provenance, not semantic
accuracy. Interpretations still need independent evaluation. No scores, treatment
recommendations, or automatic truth verdicts are intended. Coverage describes this
retrieved set, not how extensively a topic has been researched overall.

The overview is separate from retrieval: provider errors leave papers readable, partial
coverage is shown, and retry reuses successful readings. Snapshot tokens expire after
one hour (or server restart); refresh the search if expired. Snapshot, reading, and
overview caches are bounded and in-process, so this first version requires a single
backend worker or sticky routing. Shared snapshot storage is needed before using
multiple interchangeable workers. Cache keys include exact claim, source content,
integrity, and analysis version; the shared PubMed query cache is not used for synthesis.
A fresh overview can take several minutes. The reading phase allows 240 seconds,
then preserves completed work for synthesis within a 320-second overall budget.
Transient failures are retried; failed full-text readings can fall back to clearly
labeled abstracts. The search examples use the selected PMC-only or broader PubMed
mode. See [analysis recovery](docs/claims-api.md#analysis-recovery) for limits.
