# SecondOpinion

Find research behind health claims.

The app normalizes a health claim, searches PubMed, and displays related studies
with study-type labels, abstracts, and PubMed Central (PMC) access status. The
results page requests a cited research overview with individual explanations,
relevance coverage, and information gaps. The web app defaults to the PMC-only
search, which uses verified full text when available and falls back to usable
abstracts. Switching off PMC-only searches broader PubMed and analyzes abstracts.

## Local setup

For a hosted instance, see [the Render deployment guide](docs/deployment.md).
The root Dockerfile builds the React frontend and serves it with the Python API
at one origin; `render.yaml` defines a manually deployed demo service.

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
optional for claim search. The example buttons always run live searches using
the selected scope. The separate saved-examples API serves curated verdicts
from PostgreSQL and returns HTTP 503 if the database is unavailable or unconfigured.
Restart the backend after changing settings. See `.env.example` for cache options.

`GET /api/health` shows which of these are working. `status` stays `"ok"` while
the API is up, since optional services being off is not an outage:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "dependencies": {
    "azure": "configured",
    "examples_db": "reachable",
    "claim_cache": "not_configured"
  }
}
```

| Field | Values |
| --- | --- |
| `azure` | `configured` when all three Azure settings are set, otherwise `not_configured`. Read from settings only; no Azure call is made. |
| `examples_db` | `not_configured`, `reachable`, or `unreachable` (a `SELECT 1` with a 2 second limit). |
| `claim_cache` | `not_configured`, `active`, or `disabled` (configured, but the PostgreSQL layer failed and the API fell back to the in-memory cache). |

The response never includes secrets, connection strings, or hostnames.

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

Home, How it works and About have shareable URLs with browser history, page
titles and keyboard focus management. See [navigation](docs/navigation.md)
for direct-load hosting requirements and the browser regression suite.

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

Vite's preview headers are configured on the preview server. Production hosting
needs its own header configuration. If the frontend calls a separate API origin
directly, add that exact origin to frontend CSP `connect-src` and configure backend
`CORS_ORIGINS`. API policies cover handled errors and unexpected server errors
generated by FastAPI.

The optional Nginx deployment configures HTTPS redirects, HSTS, trusted
forwarding, and headers on proxy-generated errors. Verify those behaviors at
the deployed origin. [Deployment security guide](docs/security-deployment.md)

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

## Changes prompted by Rafael's review

Rafael ([@rafaelromwno](https://github.com/rafaelromwno)) opened issues #76–#83
following a security and usability review. This log records the changes merged
into `main` and the work still open in the current application.

| Feedback issue | What we changed or plan to change | Status |
| --- | --- | --- |
| [#76: Stop logging raw health claims](https://github.com/carsonful/SecondOpinion/issues/76) | Normalization logs omit claims and extracted search fields. Upstream retry logs record exception classes. | Merged in [PR #84](https://github.com/carsonful/SecondOpinion/pull/84). |
| [#77: Hide internal Azure configuration errors](https://github.com/carsonful/SecondOpinion/issues/77) | Normalization returns stable public errors. Regression tests cover redaction of configuration and provider details. | Merged in [PR #84](https://github.com/carsonful/SecondOpinion/pull/84). |
| [#78: Add HTTP security headers](https://github.com/carsonful/SecondOpinion/issues/78) | Added API headers, explicit CORS rules, and a same-origin preview policy. Added an Nginx reference deployment with HTTPS redirects, trusted proxy handling, and HTTP/TLS regression checks. | Merged in [PR #84](https://github.com/carsonful/SecondOpinion/pull/84) and [PR #91](https://github.com/carsonful/SecondOpinion/pull/91). Hosted ingress behavior still needs verification for each deployment. |
| [#79: Add a favicon](https://github.com/carsonful/SecondOpinion/issues/79) | Added the SVG favicon, multi-size ICO, and Apple touch icon based on the Second Opinion mark. | Merged in [PR #86](https://github.com/carsonful/SecondOpinion/pull/86). |
| [#80: Add a home disclaimer and shared footer](https://github.com/carsonful/SecondOpinion/issues/80) | The results screen includes a research-summary disclaimer. The proposed pre-search disclaimer and shared footer are in [PR #87](https://github.com/carsonful/SecondOpinion/pull/87). | Pre-search disclaimer and shared footer are pending on `main`. |
| [#81: Add routes, page titles, and navigation focus](https://github.com/carsonful/SecondOpinion/issues/81) | Added shareable URLs, native links, Back/Forward support, page titles, heading focus, a main landmark, and a skip link. Browser tests cover these flows, and [PR #89](https://github.com/carsonful/SecondOpinion/pull/89) added direct-load support for the Render Docker deployment. | Merged in [PR #88](https://github.com/carsonful/SecondOpinion/pull/88). |
| [#82: Address concrete accessibility findings](https://github.com/carsonful/SecondOpinion/issues/82) | Folded the original findings and broad audit #28 into [#85](https://github.com/carsonful/SecondOpinion/issues/85). The navigation work delivered the skip link, main landmark, and page-transition focus. | Navigation changes merged in [PR #88](https://github.com/carsonful/SecondOpinion/pull/88). Broader typography, contrast, tab keyboard behavior, and assistive-technology checks are tracked in #85. |
| [#83: Self-host fonts](https://github.com/carsonful/SecondOpinion/issues/83) | Bundled Comfortaa and Homemade Apple WOFF2 files and licenses, preloaded the Latin subsets, and removed third-party font loading. | Merged in [PR #84](https://github.com/carsonful/SecondOpinion/pull/84). |

Implementation is recorded in commits
[`c8063f3`](https://github.com/carsonful/SecondOpinion/commit/c8063f3)
(logging/public-error changes, alongside the separate #70 request-limit work)
and [`80e9205`](https://github.com/carsonful/SecondOpinion/commit/80e9205)
(fonts/browser policies, alongside added CI checks).

Validation for this batch: **280 backend tests passed, 8 database-dependent tests
were skipped**, and the frontend production build passed. Tests cover log
privacy, public errors, CORS, security headers, and HTTPS-only HSTS behavior.
The built app was visually checked in Firefox, and HTTP smoke checks verified
the preview security policy, all seven locally served font subsets, and license
notices. These were local checks; hosted behavior and the pending accessibility
work have not been validated. The [PR comment](https://github.com/carsonful/SecondOpinion/pull/84#issuecomment-6747611010)
records the implementation and remaining hosting work.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Status, API version, and the state of each optional dependency (see below). |
| POST | `/api/claims` | Normalize a claim and retrieve deduplicated PubMed studies with PMC access status. |
| POST | `/api/claims/overview/{analysis_id}` | Generate a cited overview for an existing search snapshot. |
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

- `frontend/src/App.tsx` and `navigation/`: page selection, routes, and navigation focus.
- `frontend/src/components/SearchScreen.tsx` and `result/`: search and results.
- `frontend/src/hooks/useClaimChecker.ts`: claim requests and request state.
- `frontend/src/data/exampleClaims.ts`: prompts for live example searches.
- `frontend/src/components/HowItWorksPage.tsx` and `how/`: educational demos for normalization, study designs, and integrity screening.
- `frontend/src/components/AboutPage.tsx` and `data/team.ts`: project and team content. Optional photos in `src/assets/team/` replace initials automatically.
- `frontend/src/styles/theme.css`: theme tokens and shared glass styles. `useTheme.ts` saves the selected theme; dark is the default.

Fonts load from bundled WOFF2 files in `frontend/public/fonts`. Search results and the
team section use light backgrounds in both themes.

## Current limits and future work

Study-type letters and colors identify research designs; they are not quality
grades. See [the study-type key](docs/study-guide.md).

Live search screens integrity notices and summarizes the retrieved research.
Future improvements include:

- **Evidence grading.** Assess study methods, relevance, and applicability for each
  outcome. Keep study design, integrity status, and access to source text visible
  alongside any grade. Validate the extraction and assessment against independently
  reviewed studies. [Evidence-grading plan](docs/evidence-grading.md)
- **Cited verdicts.** Define what evidence is sufficient to reach a conclusion.
  Compare compatible outcomes, account for overlapping studies, and show uncertainty
  or insufficient evidence when the sources cannot support a conclusion. Start with a
  bounded set of reviewed claims before expanding. [Evidence-assessment proposal](docs/evidence-assessment-options.md)

## Automatic research overview

Search returns an `analysis_id` for a trusted, immutable result snapshot. The results
page immediately displays papers and automatically calls
`POST /api/claims/overview/{analysis_id}`. The overview considers the first 20
retained papers. In PMC-only mode, Azure reads verified PMC body text up to
120,000 characters and falls back to usable abstracts when needed. In broader
PubMed mode, Azure reads abstracts. Each reading identifies its source basis,
and the overview cites analyzed papers by PMID.
Retracted papers are excluded; corrections and expressions of concern are withheld
because their effect on findings has not been resolved. Unchecked records remain
explicitly labeled. The overview reports when a paper has no usable source text.

The model selects numbered source passages; the server inserts their original text
and checks that every overview citation identifies an analyzed paper. These checks establish provenance, not semantic
accuracy. Interpretations still need independent evaluation. Coverage describes
the retrieved set. Evidence grades and verdicts are future work.

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
