# Claim retrieval API

`POST /api/claims` accepts a health-effect claim and returns candidate studies.
The `/api` prefix is required. Candidates follow PubMed relevance order after
deduplication. Provisional base design weights are included; claim assessment
and verdict generation remain separate work.

## Calling the endpoint

Local base URL: `http://localhost:8000`. Interactive documentation is at `/docs`;
the full machine-readable request and response schemas are at `/openapi.json`.
A deployed base URL has not yet been configured in this repository.

```bash
curl --fail-with-body http://localhost:8000/api/claims \
  -H 'Content-Type: application/json' \
  -d '{"claim":"Does zinc help with the common cold?","limit":5}'
```

| Request field | Contract |
| --- | --- |
| `claim` | Required string, 1–2,000 characters. Blank input is rejected and surrounding whitespace is removed. Submit one health-effect claim or question. |
| `limit` | Optional integer, 1–100; defaults to 20. Limits retrieved PubMed records before deduplication. |

Unknown request fields are rejected. The response can contain fewer candidates
than `limit`, including an empty list with HTTP 200.

## Successful response

| Field | Meaning |
| --- | --- |
| `status` | Always `"candidates"`. |
| `claim` | Submitted claim with surrounding whitespace removed. |
| `normalized` | `query`, `intervention`, `outcome`, nullable `population`, `relation`, `negated`, and `version` (`"foundry-v1"`). |
| `query_translation` | PubMed's interpretation of the query, or `null`. |
| `total_results` | Total PubMed matches before limiting and deduplication. This is not the length of `candidates`. |
| `candidates` | Ordered array of `{ "article": ..., "integrity": ..., "metadata": ..., "weight": ... }`. |

Each `article` contains `pmid`, `title`, nullable `abstract`, nullable `journal`,
nullable `year`, `authors`, nullable `doi`, nullable `pmc_id`,
`publication_types`, `mesh_terms`, `retracted`, and `url`. Lists can be empty.

Each `integrity` contains `status` and `notices`. Status is one of `no_notice_found`,
`corrected`, `retracted`, `expression_of_concern`, or `unchecked`. Check the status before
presenting a study: retracted studies and those with an expression of concern remain in the response for
display, and `unchecked` does not mean trustworthy. Each notice includes
`category`, `crossref_type`, nullable `label`, nullable `notice_doi`, nullable
`notice_url`, nullable `published_on` (ISO date), and `sources`.

Duplicates are removed using PMID and normalized DOI, preserving the first
occurrence's position. Retraction markers on duplicate records are retained.
No computed verdict or confidence score is returned.

Each `metadata` contains `design` (the canonical identifier documented in
`evidence-grading.md`), `design_reason`, nullable `design_evidence`, nullable
`sample_size`, nullable `sample_size_evidence`, `sample_size_reason`, and
`animal_only`. Year and journal remain on `article` and can be null. The raw
publication tags remain available on `article.publication_types`.

Designs come from indexed publication types. Confirmed observational evidence
can be refined to cohort, case-control, or cross-sectional only when the abstract
explicitly describes its own design. Conflicting tags remain unknown. Generic
Journal Article or Letter tags alone do not establish a design. Syntheses do
not automatically inherit a primary design from a publication tag.

Participant counts require an explicit total enrollment/recruitment statement
in the abstract. Missing, conflicting, planned, per-group, or unresolved counts
remain null. Reviews and commentary do not receive primary-study counts. This
conservative extractor does not sum study arms or infer totals from other numbers.
Supporting abstract passages are returned for inspection.

Each `weight` contains nullable `base_weight`, nullable `final_weight`, `version`,
`reason`, and `eligibility_reason`. The base weight uses the configured design
ladder; unknown designs and syntheses with unresolved included designs remain
null. A base weight is not a confidence percentage. `final_weight` is zero for
retracted or withheld studies, and otherwise null pending claim assessment.
The base weight is retained even when the integrity gate blocks contribution.

The frontend displays these fields in an expandable table with source and
notice links. Sort options are search relevance, base weight descending, year
descending, and study type alphabetically; unknown values sort last. Sorting
by base weight includes blocked studies with their integrity labels and does
not change their final contributions. The table contains its horizontal scrolling.

## Error handling

| HTTP status | Meaning | Frontend behavior |
| --- | --- | --- |
| 422 | Invalid request or input is not one clear health claim. | Ask the user to correct the input. |
| 502 | An evidence source returned an unusable response. | Show a service error and allow retry. |
| 503 | Azure normalization is unconfigured/unavailable, or PubMed/Crossref is unavailable. | Show a service error and allow retry. Rephrasing does not fix service configuration. |

Errors have a JSON `detail` field. Request-validation errors use an array of
validation details; normalization and service errors use a string. The endpoint
does not return partial candidates when an integrity check fails.

## Frontend integration and hosting

The local Vite server proxies `/api` to port 8000. For a separately hosted
frontend, send requests to the deployed API base URL and set the backend's
`CORS_ORIGINS` to a JSON array containing that frontend's exact origin. Vite's
development proxy does not run in a production frontend build.

The backend requires `AZURE_INFERENCE_ENDPOINT`, `AZURE_MODEL_DEPLOYMENT_NAME`,
and `AZURE_INFERENCE_API_KEY`; see `backend/.env.example` for their meanings.
PostgreSQL is optional for this endpoint. Leave `DATABASE_URL` unset when no
database is available. The saved examples require PostgreSQL separately.

Start a hosted backend from the `backend` directory using
`uvicorn app.main:app --host 0.0.0.0 --port <service-port>` after installing
`requirements.txt`. Configure credentials through the host's environment
settings. Use `/api/health` for the process health check; it does not probe
Azure, PubMed, or Crossref.

Before marking issue #16 complete, deploy the backend, verify a real request
against its HTTPS URL, and verify that the frontend can call it from its hosted
origin. Publish that base URL alongside `/docs` and `/openapi.json`.
