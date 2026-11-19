# Deploying browser security policies

The configuration in `deploy/nginx` serves the built frontend and proxies the API
from one HTTPS origin. This closes the gap between Vite preview headers and static
hosting: preview settings do not travel with `frontend/dist`.

## Deployment layout

Use Nginx as the public TLS endpoint and one Uvicorn worker on the same machine.
The supplied configuration assumes the frontend build is at
`/srv/secondopinion/frontend/dist` and Uvicorn listens on `127.0.0.1:8001`.
Only ports 80 and 443 should be public. The one-worker choice also preserves the
existing in-process overview snapshots and request limits.

1. Build the frontend with `npm ci` and `npm run build` in `frontend/`, then copy
   `dist` to the configured document root. Keep the application source and `.env`
   outside that root.
2. Install Nginx with TLS support. Put `headers.conf` and `proxy.conf` from
   `deploy/nginx/` in `/etc/nginx/secondopinion/`.
3. Copy `secondopinion.conf` into the directory included by Nginx's `http` block,
   commonly `/etc/nginx/conf.d/`. Replace every `secondopinion.example` occurrence,
   the document root, and both certificate paths. Use a valid certificate chain.
4. Start the backend from `backend/` with the following arguments. Keep its
   existing environment settings and set `CORS_ORIGINS` to the actual frontend
   origin as a JSON array, such as `["https://secondopinion.example"]`.

```sh
uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1 \
  --proxy-headers --forwarded-allow-ips 127.0.0.1
```

5. Validate with `nginx -t`, then reload Nginx through the host's service manager.
   Remove any conflicting default virtual host. Test the real domain using the
   command below before considering hosted verification complete.

The example assumes Nginx directly receives public traffic. If another trusted
load balancer terminates TLS first, adapt the trusted-peer and scheme handling at
that boundary. Do not blindly trust caller-supplied forwarding headers or use
`--forwarded-allow-ips '*'` on an exposed backend. Nginx replaces forwarded client
and scheme headers with the connection facts it observes. Direct backend access
would bypass that boundary, so the loopback binding is part of the setup.

## What the configuration guarantees

| Response | Policy |
| --- | --- |
| HTML, JavaScript, fonts and static errors | Same CSP as production preview; scripts, fonts and API connections use the same origin. React's existing inline styles remain allowed. |
| API responses, OpenAPI and proxy errors | A restrictive JSON policy plus framing, content sniffing, referrer and permissions protections. |
| `/docs`, `/redoc` and OAuth documentation redirect | Other headers remain; the JSON-only CSP is omitted so FastAPI's documentation assets still load. |
| HTTPS | One HSTS header with a one-year lifetime. |
| HTTP | A 308 redirect to the configured HTTPS origin. No HSTS is emitted on HTTP. |
| `/about` and `/how-it-works`, including a trailing slash | The SPA entry point, so a direct visit or refresh works after the routing change. |
| Missing assets, fonts, API routes and unknown page paths | Their real error response instead of a successful `index.html` response. |

Headers use `always`, so Nginx-generated errors are covered. The edge replaces
upstream security headers to avoid duplicate policies. Keep new `add_header`
directives in the shared file: adding one inside a location can disable inherited
headers in older Nginx versions. Access logs omit query strings. Configure log
retention separately for the host and upstream services.

CORS remains owned by FastAPI. It limits browser API access using explicit origins,
GET, POST and OPTIONS, and approved request headers. The CSP `connect-src` setting
separately controls destinations contacted by the frontend. Serving both behind
one origin requires no CSP exception. A separate API origin requires an exact CSP
addition and a corresponding CORS configuration change, followed by verification.
Local Vite development on `localhost:5173` continues to use its existing proxy and
the default CORS configuration. These deployment files are opt-in.

## Verify the deployed origin

From the repository root:

```sh
python3 tools/check_deployment.py https://secondopinion.example \
  --http-url http://secondopinion.example
```

The script produces a JSON report and exits nonzero on failure. Its nine HTTPS
probes and optional HTTP redirect probe use GET only. They do not normalize claims,
run searches, request overviews, or consume Azure credits. TLS is always verified;
`--ca-file /path/to/local-ca.pem` supports a trusted local test certificate.
The checker does not prove that every external service or every app feature works.

## Regression tests and recorded validation

```sh
NGINX_BIN=/path/to/nginx python3 -m unittest discover -s tests/deployment -v
```

With Nginx on `PATH`, `NGINX_BIN` can be omitted. The tests start isolated listeners
on ephemeral loopback ports, create a short-lived local TLS certificate and render
the checked-in configuration with temporary paths. Nginx serves files and performs
actual proxying. The upstream HTTP application is a controlled fixture, allowing
handled 500s and connection failures to be reproduced without live API calls.

On November 14, 2026, all **23 tests passed locally**, with no skips, using Nginx
1.28.0 built from its official source and Python 3.12. The checks cover HTTP redirects,
verified TLS and rejected untrusted certificates, real files and missing files,
deep links, header uniqueness, preview CSP parity, 404s, handled 500s, edge 502s,
hidden files, and forged forwarding headers. Negative checker tests also cover
incorrect statuses and content types, malformed health responses, transport
failures, invalid timeouts, incorrect redirects, and a failing process exit status.
The Deployment policies workflow runs
the same suite using the runner's Nginx package and Python 3.11, without secrets.

No public production origin was supplied or deployed during this work. Run the
verification command against the actual host after applying this configuration.

## Assistance and references

Configuration, verification tooling, tests and this runbook were developed with
ChatGPT assistance. The three commits are tagged `[ai-assisted]`. Reviewers should
read the policy maps, proxy trust boundary and test cases before merging.

- [Nginx header inheritance and `always`](https://nginx.org/en/docs/http/ngx_http_headers_module.html)
- [Nginx `try_files`](https://nginx.org/en/docs/http/ngx_http_core_module.html#try_files)
- [Uvicorn proxy settings](https://www.uvicorn.org/settings/#http)
