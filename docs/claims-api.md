# Claim search API

`POST /api/claims` normalizes a health-effect claim, searches PubMed, and checks
whether PMC body text can be retrieved. Study-type labels and access status are
descriptive metadata; the endpoint returns no evidence grades or claim verdict.
Evidence grading is planned for a future release; proposed rules are documented
in [the evidence-grading plan](evidence-grading.md).

## Request

Local base URL: `http://localhost:8000`. Interactive documentation is at
`/docs`; the machine-readable schema is at `/openapi.json`.

```json
{"claim":"Does zinc help with the common cold?","limit":5}
```

`claim` is required (1–2,000 characters); `limit` is optional (1–100, default
20). Unknown fields are rejected.

## Response

The response includes the normalized query, PubMed result count, candidate
studies in PubMed relevance order, and `coverage` counts for retrieved full
text, abstract-only records, and citation-only records. Each candidate contains:

- `article`: PubMed citation, abstract, publication types, and links.
- `metadata`: study design label.
- `access`: `level` (`full_text`, `abstract_only`, or `metadata_only`), reason,
  detail, PMC ID/link, license, and retrieved body section names.

The UI uses a color and letter beside the study type as a quick identifier.
These marks describe design categories, not quality. See the [study type key](study-guide.md).

## Full-text access

The backend uses validated PMC IDs from authoritative PubMed records and the
fixed [NCBI BioC PMC API](https://www.ncbi.nlm.nih.gov/research/bionlp/APIs/BioC-PMC/).
It verifies PMCID and PMID identity and requires body text beyond the abstract.
It does not scrape publishers, use subscription sessions, or retrieve PDFs.

When text is unavailable or cannot be verified, the citation remains in the
response. Failure reasons distinguish missing IDs, no PMC text, retrieval
errors, parse errors, and size limits. An unavailable record is not treated as
a paywall or a quality judgment. Access counts describe retrieval only.

Requests share PubMed's NCBI rate limiter, allow three simultaneous PMC
downloads, retry transient HTTP errors once, and have a 25-second deadline.
Responses over 3 MB or body text over 600,000 characters are not retained.
Verified documents are cached in memory for 24 hours (up to 64 documents).
`?refresh=true` skips search and document cache reads. Temporary retrieval
failures are not cached.

## Errors and caching

Invalid claims return 422; unavailable normalization or evidence services return
503; unusable PubMed responses return 502.

Repeated claims are served from an in-memory cache keyed by normalized query and
limit. Add `?refresh=true` to fetch fresh results. Entries expire after six
hours (`CLAIMS_CACHE_TTL_SECONDS`, `0` disables caching), with at most 256
local entries (`CLAIMS_CACHE_MAX_ENTRIES`). Without further configuration, the
cache clears when the backend restarts.

To share claim results across processes and restarts, set `CACHE_DATABASE_URL`
to a **separate PostgreSQL database**. It must have a different database name
from `DATABASE_URL`, which is reserved for saved verdict examples. Startup
creates only `claim_cache_entries` in the cache database. The existing claim
endpoint, response shape, and default in-memory behavior remain the same.
After a local miss, the backend reads the shared cache before calling Azure,
PubMed, or PMC. A shared hit sets `cached: true` and makes no calls to those
services. Failed PMC retrievals are not stored. If the cache database becomes
unavailable, requests continue through the existing in-memory/live path; restart
the backend after restoring the database to re-enable the shared cache.

The PostgreSQL TTL uses `CLAIMS_CACHE_TTL_SECONDS`. Expired rows are removed at
backend startup or with `prune`. Local copies expire within
60 seconds when PostgreSQL is enabled so manual changes become visible. A
refresh request skips both caches and replaces the saved result after successful
retrieval. Set the TTL to `0` to disable both caches.

### Manually add or inspect a cached claim

From `backend/`, use a complete JSON response from `POST /api/claims`, or write
one matching its schema at `/openapi.json`. The file must include the original
`claim`, `normalized` fields, `coverage`, and the complete `candidates` array.
The command validates the response and its coverage counts before writing.
The `--limit` value must match the request you intend to cache (default `20`).

```bash
python -m app.cache_admin validate /path/to/claim-result.json --limit 20
python -m app.cache_admin put /path/to/claim-result.json --limit 20
python -m app.cache_admin get 'Does zinc help with colds?' --limit 20
python -m app.cache_admin stats
python -m app.cache_admin delete 'Does zinc help with colds?' --limit 20
python -m app.cache_admin prune
```

`validate` works without a database connection, so a hand-edited file can be
checked before loading it. The saved claim wording is matched case and
whitespace insensitively. Another
wording can reuse the candidate result if its normalized search query matches,
but normalizing that new wording still needs Azure once. `get` prints a valid
JSON response with `cached: true`; `delete` removes the matching wording and
candidate result for the supplied limit. Running `put` again replaces that
entry and resets its TTL. Active backend processes may serve an earlier local
copy for up to 60 seconds. These are claim search candidates, not the curated
verdicts returned by `GET /api/examples/{slug}`.

## Local setup

The backend requires `AZURE_INFERENCE_ENDPOINT`,
`AZURE_MODEL_DEPLOYMENT_NAME`, and `AZURE_INFERENCE_API_KEY` for claim
normalization of uncached claims. PostgreSQL is optional for claim search; saved
verdict examples use `DATABASE_URL` separately. The local Vite server proxies
`/api` to port 8000. A hosted
frontend needs the backend base URL and its origin in `CORS_ORIGINS`.
