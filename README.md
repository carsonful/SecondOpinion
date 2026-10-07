# SecondOpinion
Busting health myths backed by science.

## Project structure

- `frontend/` — React + TypeScript (Vite)
- `backend/` — Python API (FastAPI)

## Getting started

### PubMed database and ingestion

Requires Docker with Compose, Python 3.11+, and enough disk space for the
chosen PubMed files and embeddings. From the repository root:

```bash
docker compose up -d
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Uncomment NCBI_EMAIL in .env and use your real contact address.
alembic upgrade head
python -m app.cli sample --query "randomized controlled trial" --limit 10
python -m app.cli stats
```

`DATABASE_URL` in `backend/.env` defaults to the Compose database. It must be a
`postgresql+psycopg://` URL, and the database role must be allowed to create
the `vector` extension. `NCBI_EMAIL` is required for sample imports;
`NCBI_API_KEY` is optional. The importer uses NCBI E-utilities for samples and
the [official PubMed FTP mirror](https://ftp.ncbi.nlm.nih.gov/pubmed/) for bulk
files. Keep the database port private when deploying beyond a laptop.

For a baseline file and official daily updates:

```bash
mkdir -p pubmed-baseline
curl -L --fail -o pubmed-baseline/pubmed26n0001.xml.gz https://ftp.ncbi.nlm.nih.gov/pubmed/baseline/pubmed26n0001.xml.gz
python -m app.cli baseline pubmed-baseline/pubmed26n0001.xml.gz
python -m app.cli sync-updates --directory pubmed-updatefiles
# Or import already downloaded update files:
python -m app.cli updates pubmed-updatefiles/
```

`sync-updates` lists the official update directory, downloads missing files,
checks their published MD5 values, and applies them in filename order. It can
be run daily. For a limited run, pass `--start-at pubmed26n1335.xml.gz`
and/or `--max-files 1`. Apply a complete annual baseline before its updates.
Each XML or XML.GZ file is parsed as a stream; batches and their checkpoints
commit together. Restart the same command after interruption to resume at the
last committed record. Updated PMIDs overwrite earlier metadata. Deletion
notices retain a study tombstone and remove its embedding, preserving evidence
foreign keys. Files are identified by path, size, and modification time.

Embeddings are an independent CPU job. Install the optional model dependency
and run it after importing metadata:

```bash
pip install 'torch==2.5.1+cpu' --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-embeddings.txt
python -m app.cli embed --batch-size 64
python -m app.cli stats
```

The default model is `sentence-transformers/all-MiniLM-L6-v2`, pinned to
revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. The model and revision
are stored beside each 384-dimensional vector. A content hash of title and
abstract prevents repeated inference for unchanged records. Re-run `embed`
after updates; modified records are refreshed. `--model` and `--revision`
permit replacing the encoder with another 384-dimensional model. A different
vector dimension needs a schema migration. To test just a few records, use
`--limit 10`.

To verify migrations in both directions on a **disposable** database:

```bash
docker compose exec db createdb -U secondopinion secondopinion_test
export TEST_DATABASE_URL=postgresql+psycopg://secondopinion:secondopinion@localhost:5432/secondopinion_test
DATABASE_URL="$TEST_DATABASE_URL" alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" alembic downgrade base
DATABASE_URL="$TEST_DATABASE_URL" alembic upgrade head
pytest -q
```

The integration tests drop and recreate their target schema. Create a separate
`secondopinion_test` database before setting `TEST_DATABASE_URL`; CI does this
with a pgvector PostgreSQL service. `alembic downgrade base` drops all data
created by this migration.

The proposed schema follows [issue #3](https://github.com/carsonful/SecondOpinion/issues/3):
`claims` has many `evidence_scores`, each score belongs to one `study`, and a
claim has at most one `verdict`. Each study has at most one current embedding.
`ingestion_checkpoints` records committed file progress. PMID is mandatory and
unique; DOI, title, abstract, journal, exact publication date, study type,
sample size, retraction status and MeSH terms are nullable because PubMed does
not provide all of them for every citation. Partial dates are retained in
metadata rather than invented. The schema adds a combined title/abstract GIN
index and a cosine HNSW index on embeddings. Issue #3 still requires the four
named approvers; this migration is a proposal until they approve it. The 20
claim fixture from [issue #8](https://github.com/carsonful/SecondOpinion/issues/8)
has not been merged, so there is no seed script or fabricated claims in this PR.

Local verification on October 7, 2026 used PostgreSQL 17.11 with pgvector
0.8.1. The streaming parser read all 30,000 citations in official baseline
`pubmed26n0001.xml.gz` without importing that file. Five genuine E-utilities
records (PMIDs 41726474, 41421800, 41263061, 41220063, 41194612) were
imported from a saved XML response. The CPU job wrote five 384-dimensional
vectors; a second run scanned five and skipped all five unchanged records.
The local PostgreSQL suite passed 5 tests, and upgrade → downgrade → upgrade
plus `alembic check` succeeded. These counts describe a small development run,
not the full PubMed corpus.

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
