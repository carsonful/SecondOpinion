# Deploy the first instance

Use one Render Docker web service for the initial demo. The image builds React
with Node 22, then runs FastAPI with Python 3.11 as a non-root user. The frontend
and `/api` share an origin, including on direct visits to `/about` and
`/how-it-works`. API and missing-asset errors keep their real HTTP status.

Netlify can host the frontend, but cannot run this persistent Python API as a
static site. Its [external proxy rewrites time out after 26 seconds](https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/),
while Azure normalization allows 60 seconds. Hosting the whole app on Render
avoids that extra timeout and a second host to configure.

## Launch on Render

1. Commit and push these deployment changes to the GitHub branch to deploy.
2. Open [Render](https://dashboard.render.com/), choose **New → Blueprint**,
   connect `carsonful/SecondOpinion`, and select that branch. Render reads the
   root `render.yaml`. Review the service name and plan before creating it.
3. Enter the three prompted Azure values: `AZURE_INFERENCE_ENDPOINT`,
   `AZURE_MODEL_DEPLOYMENT_NAME`, and `AZURE_INFERENCE_API_KEY`. Use the resource
   endpoint and exact deployment name described in `backend/.env.example`.
   Enter secrets in Render's environment settings, never in Git or build args.
4. Create the service. Its first deployment builds the root `Dockerfile`.
   Subsequent deployments are manual (`autoDeployTrigger: off`). Once CI and
   hosted checks are established, `checksPass` can enable CI-gated deployment.
5. Open the assigned HTTPS `onrender.com` address. No frontend API URL or CORS
   origin changes are required: the frontend uses relative `/api` URLs.

The blueprint requests a free demo instance and provisions no database. Review
[free-instance limitations](https://render.com/docs/free), including idle
spin-down and cold starts, before using it beyond a demo. Azure usage is billed
separately. For an always-on instance, select a paid plan in Render after
reviewing its current price.

Optional environment values can be added to the service:

| Setting | When to set it |
| --- | --- |
| `NCBI_EMAIL`, `CROSSREF_MAILTO` | Contact email for upstream research services. |
| `NCBI_API_KEY` | Higher shared PubMed request rate. |
| `DATABASE_URL` | PostgreSQL for the saved-examples API. The frontend example buttons run live searches with either database configuration. |
| `CACHE_DATABASE_URL` | Persistent claim cache, with a different database name from `DATABASE_URL`. |

Docker copies only application code, runtime requirements, and the built public
frontend into the final image. Local `.env` files are excluded from the build
context. CORS is empty for the same-origin deployment. API docs remain at
`/docs`, with the OpenAPI contract at `/openapi.json`.

## Verify the hosted instance

- `GET /api/health` returns `status: "ok"` and `dependencies.azure: "configured"`.
  This confirms configuration presence, not Azure authentication or model reachability.
- Visit `/`, `/about`, and `/how-it-works` directly and refresh each. Check
  Back/Forward navigation, favicon, and local fonts.
- Submit one real claim and allow the research overview to finish. This is the
  live check of Azure, PubMed, and overview generation; a passing health check
  alone does not establish that those integrations work.
- `/api/not-a-route` and `/assets/not-a-file.js` return 404, not the app HTML.
- Inspect document and API response headers for CSP, `X-Frame-Options`, and
  `X-Content-Type-Options`. Confirm Render redirects HTTP to HTTPS.

The container runs one worker, preserving the existing process-local cache and
rate limit. It disables forwarded-header trust, so behind Render's ingress the
10-per-minute inference quota may be shared by visitors reaching the same proxy.
Before broad public use, configure a verified trusted ingress range or a gateway
with shared client limits; do not simply trust arbitrary forwarded client IPs.
This also means application HSTS is not emitted for TLS terminated at ingress:
verify or configure HSTS at the hosting edge before a production rollout.
Access logging is disabled in Uvicorn; configure Render and Azure log retention
separately. No global Azure spending cap or user authentication is introduced.

## Reproduce locally

With Docker installed:

```sh
docker build -t secondopinion .
docker run --rm -p 10000:10000 --env-file backend/.env secondopinion
```

Visit `http://localhost:10000`. For an application-only check without Docker,
build `frontend` using `npm ci && npm run build`, then run from `backend`:

```sh
FRONTEND_DIST=../frontend/dist .venv/bin/uvicorn app.main:app --port 10000 --no-proxy-headers --no-access-log
```

Render follows the image's command, binding `0.0.0.0` on its `PORT` environment
variable (default 10000), and monitors `/api/health`. See
[Docker hosting](https://render.com/docs/docker) and the
[Blueprint reference](https://render.com/docs/blueprint-spec).

To roll back, redeploy a previous successful deployment from Render's dashboard.
Optional PostgreSQL data persists independently and is not rolled back with code.
