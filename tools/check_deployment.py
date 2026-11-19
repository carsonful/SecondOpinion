#!/usr/bin/env python3
"""Read-only HTTP checks for the deployment in deploy/nginx.

The probes never submit a claim, request an overview, or call an upstream model.
TLS certificates are verified, including when an explicit local CA is supplied.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import ssl
import sys
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Response:
    status: int
    headers: list[tuple[str, str]]
    body: bytes

    def values(self, name: str) -> list[str]:
        return [value for key, value in self.headers if key.lower() == name.lower()]


@dataclass(frozen=True)
class Check:
    path: str
    ok: bool
    problems: list[str]


def origin(value: str, scheme: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != scheme or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
    ):
        raise ValueError(f"Expected a {scheme} origin without credentials or a path")
    _ = parsed.port
    return f"{scheme}://{parsed.netloc}"


def request(base: str, path: str, context: ssl.SSLContext, timeout: float) -> Response:
    parsed = urlsplit(base)
    if parsed.scheme == "https":
        connection = http.client.HTTPSConnection(
            parsed.hostname, parsed.port, timeout=timeout, context=context,
        )
    else:
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
    try:
        connection.request("GET", path, headers={"User-Agent": "SecondOpinion-header-check/1"})
        response = connection.getresponse()
        return Response(response.status, response.getheaders(), response.read(1024 * 1024))
    finally:
        connection.close()


def policy(value: str) -> dict[str, set[str]]:
    directives: dict[str, set[str]] = {}
    for item in value.split(";"):
        words = item.split()
        if words:
            if words[0] in directives:
                raise ValueError(f"Duplicate CSP directive: {words[0]}")
            directives[words[0]] = set(words[1:])
    return directives


def check_headers(response: Response, *, kind: str, https: bool) -> list[str]:
    errors: list[str] = []
    for name, expected in {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    }.items():
        if response.values(name) != [expected]:
            errors.append(f"{name} must occur once with the configured value")
    hsts = response.values("Strict-Transport-Security")
    if hsts != (["max-age=31536000"] if https else []):
        errors.append("HSTS must occur once over HTTPS and never over HTTP")
    values = response.values("Content-Security-Policy")
    if kind == "docs":
        if values:
            errors.append("Interactive API docs unexpectedly received a restrictive CSP")
        return errors
    if len(values) != 1:
        return [*errors, "Expected exactly one Content-Security-Policy header"]
    try:
        actual = policy(values[0])
    except ValueError as error:
        return [*errors, str(error)]
    expected = {
        "default-src": {"'none'"} if kind == "api" else {"'self'"},
        "frame-ancestors": {"'none'"},
        "base-uri": {"'none'"} if kind == "api" else {"'self'"},
        "form-action": {"'none'"} if kind == "api" else {"'self'"},
    }
    if kind == "spa":
        expected.update({
            "script-src": {"'self'"}, "font-src": {"'self'"},
            "connect-src": {"'self'"}, "object-src": {"'none'"},
            "style-src": {"'self'", "'unsafe-inline'"},
            "img-src": {"'self'", "data:"},
        })
    if actual.keys() != expected.keys():
        errors.append("Unexpected CSP directives could override the configured restrictions")
    for directive, tokens in expected.items():
        if actual.get(directive) != tokens:
            errors.append(f"Unexpected CSP {directive}")
    return errors


def check_site(base: str, *, context: ssl.SSLContext, timeout: float = 10) -> list[Check]:
    results: list[Check] = []
    probes = [
        ("/", 200, "spa", "text/html"),
        ("/about", 200, "spa", "text/html"),
        ("/how-it-works", 200, "spa", "text/html"),
        ("/api/health", 200, "api", "application/json"),
        ("/api/__header_probe_missing__", 404, "api", "application/json"),
        ("/assets/__header_probe_missing__.js", 404, "spa", None),
        ("/fonts/__header_probe_missing__.woff2", 404, "spa", None),
        ("/docs", 200, "docs", "text/html"),
        ("/openapi.json", 200, "api", "application/json"),
    ]
    for path, status, kind, content_type in probes:
        try:
            response = request(base, path, context, timeout)
            problems = check_headers(response, kind=kind, https=True)
            if response.status != status:
                problems.append(f"Expected HTTP {status}, received {response.status}")
            if content_type and not any(
                value.partition(";")[0].strip().lower() == content_type
                for value in response.values("Content-Type")
            ):
                problems.append(f"Expected {content_type} content")
            if path == "/api/health" and response.status == 200:
                try:
                    if json.loads(response.body).get("status") != "ok":
                        problems.append("API health response did not report status ok")
                except (ValueError, AttributeError):
                    problems.append("API health response was not a JSON object")
            results.append(Check(path, not problems, problems))
        except (OSError, http.client.HTTPException) as error:
            results.append(Check(path, False, [f"Request failed: {type(error).__name__}"]))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="Public HTTPS origin, without a path")
    parser.add_argument("--http-url", help="Also check the HTTP to HTTPS redirect")
    parser.add_argument("--ca-file", help="Additional trusted CA for local TLS verification")
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args(argv)
    try:
        base = origin(args.base_url, "https")
        http_base = origin(args.http_url, "http") if args.http_url else None
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("Timeout must be a finite positive number")
        context = ssl.create_default_context(cafile=args.ca_file)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    checks = check_site(base, context=context, timeout=args.timeout)
    if http_base:
        path = "/about?header-check=1"
        try:
            response = request(http_base, path, context, args.timeout)
            problems = check_headers(response, kind="spa", https=False)
            if response.status != 308 or response.values("Location") != [base + path]:
                problems.append("HTTP must redirect to the configured HTTPS origin with the path intact")
            checks.append(Check("HTTP redirect", not problems, problems))
        except (OSError, http.client.HTTPException) as error:
            checks.append(Check("HTTP redirect", False, [type(error).__name__]))
    print(json.dumps({"checks": [asdict(item) for item in checks]}, indent=2))
    return 0 if all(item.ok for item in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
