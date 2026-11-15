"""Exercise the checked-in Nginx configuration over real HTTP and verified TLS.

Run with: NGINX_BIN=/path/to/nginx python -m unittest discover -s tests/deployment -v
Only the upstream fixture is synthetic. Nginx, TLS, files and proxying are real.
"""

from __future__ import annotations

import http.client
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.check_deployment import Check, Response, check_headers, check_site, main, origin, policy, request

NGINX = os.environ.get("NGINX_BIN") or shutil.which("nginx")


class Upstream(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/disconnect":
            self.connection.close()
            return
        status = 200
        if self.path in {"/api/health", "/api/headers"}:
            body = json.dumps({
                "status": "ok", "forwarded_for": self.headers.get("X-Forwarded-For"),
                "proto": self.headers.get("X-Forwarded-Proto"),
                "forwarded": self.headers.get("Forwarded"),
            }).encode()
        elif self.path == "/openapi.json":
            body = b'{"openapi":"3.1.0"}'
        elif self.path in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
            body = b"<!doctype html><title>API docs</title>"
        else:
            status = 500 if self.path == "/api/failure" else 404
            body = b'{"detail":"fixture error"}'
        self.send_response(status)
        self.send_header("Content-Type", "text/html" if self.path.startswith(("/docs", "/redoc")) else "application/json")
        self.send_header("Content-Length", str(len(body)))
        # Prove that the edge does not append duplicate policies from the API.
        self.send_header("Content-Security-Policy", "default-src *")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Strict-Transport-Security", "max-age=1")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def port() -> int:
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        return bound.getsockname()[1]


@unittest.skipUnless(NGINX and shutil.which("openssl"), "Nginx and openssl are required")
class NginxContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="secondopinion-edge-")
        cls.addClassCleanup(cls.directory.cleanup)
        work = Path(cls.directory.name)
        (work / "logs").mkdir()
        dist = work / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "fonts").mkdir()
        (dist / "index.html").write_text('<!doctype html><title>Second Opinion</title><main id="root"></main>')
        (dist / "assets/app.js").write_text("window.loaded = true;")
        (dist / "fonts/example.woff2").write_bytes(b"font fixture")
        (dist / ".env").write_text("must not be served")
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        cls.addClassCleanup(cls.upstream.server_close)
        cls.addClassCleanup(cls.upstream.shutdown)
        threading.Thread(target=cls.upstream.serve_forever, daemon=True).start()
        cls.http_port, cls.https_port = port(), port()
        cls.base = f"https://127.0.0.1:{cls.https_port}"
        cert, key = work / "cert.pem", work / "key.pem"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert), "-days", "1",
            "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ], check=True, capture_output=True)
        cls.context = ssl.create_default_context(cafile=str(cert))
        source = ROOT / "deploy/nginx"
        proxy = (source / "proxy.conf").read_text().replace(
            "127.0.0.1:8001", f"127.0.0.1:{cls.upstream.server_port}",
        )
        (work / "proxy.conf").write_text(proxy)
        shutil.copyfile(source / "headers.conf", work / "headers.conf")
        site = (source / "secondopinion.conf").read_text()
        for before, after in {
            "https://secondopinion.example": cls.base,
            "secondopinion.example": "127.0.0.1",
            "listen 80;": f"listen 127.0.0.1:{cls.http_port};",
            "listen 443 ssl;": f"listen 127.0.0.1:{cls.https_port} ssl;",
            "/etc/nginx/secondopinion": str(work),
            "/etc/ssl/secondopinion/fullchain.pem": str(cert),
            "/etc/ssl/secondopinion/privkey.pem": str(key),
            "/srv/secondopinion/frontend/dist": str(dist),
            "/var/log/nginx/secondopinion.access.log": str(work / "access.log"),
        }.items():
            site = site.replace(before, after)
        (work / "site.conf").write_text(site)
        config = work / "nginx.conf"
        config.write_text(
            f"pid {work}/nginx.pid;\nerror_log {work}/error.log;\nevents {{}}\n"
            f"http {{ types {{ text/html html; application/javascript js; font/woff2 woff2; }}\n"
            f"include {work}/site.conf; }}\n"
        )
        command = [NGINX, "-p", str(work), "-c", str(config)]
        subprocess.run([*command, "-t"], check=True, capture_output=True)
        cls.nginx = subprocess.Popen([*command, "-g", "daemon off;"], stderr=subprocess.PIPE)
        cls.addClassCleanup(cls.stop_nginx)
        for _ in range(100):
            if cls.nginx.poll() is not None:
                raise RuntimeError(cls.nginx.stderr.read().decode())
            try:
                with socket.create_connection(("127.0.0.1", cls.https_port), timeout=.1):
                    break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError("Nginx did not start")
        cls.cert = cert

    @classmethod
    def stop_nginx(cls):
        cls.nginx.terminate()
        try:
            cls.nginx.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.nginx.kill()
            cls.nginx.wait(timeout=5)
        cls.nginx.stderr.close()

    def get(self, path, *, tls=True, headers=None):
        connection = (
            http.client.HTTPSConnection("127.0.0.1", self.https_port, context=self.context, timeout=5)
            if tls else http.client.HTTPConnection("127.0.0.1", self.http_port, timeout=5)
        )
        try:
            connection.request("GET", path, headers=headers or {})
            result = connection.getresponse()
            return Response(result.status, result.getheaders(), result.read())
        finally:
            connection.close()

    def test_pages_and_deep_links_serve_the_spa_with_https_policies(self):
        for path in ["/", "/about", "/how-it-works", "/about/?source=test"]:
            with self.subTest(path=path):
                result = self.get(path)
                self.assertEqual(result.status, 200)
                self.assertIn(b'id="root"', result.body)
                self.assertEqual(check_headers(result, kind="spa", https=True), [])

    def test_static_csp_matches_the_vite_preview_policy(self):
        source = (ROOT / "frontend/securityHeaders.ts").read_text()
        directives = re.findall(r'^\s*"([^"\n]+)",?\s*$', source, re.MULTILINE)
        actual = self.get("/").values("Content-Security-Policy")[0]
        self.assertEqual(policy(actual), policy("; ".join(directives)))

    def test_tls_certificate_verification_is_not_bypassed(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            request(self.base, "/", ssl.create_default_context(), 5)

    def test_assets_are_real_files_and_missing_files_stay_404(self):
        for path, status in [("/assets/app.js", 200), ("/fonts/example.woff2", 200),
                             ("/assets/missing.js", 404), ("/fonts/missing.woff2", 404),
                             ("/not-a-page", 404)]:
            with self.subTest(path=path):
                result = self.get(path)
                self.assertEqual(result.status, status)
                self.assertNotIn(b'id="root"', result.body)
                self.assertEqual(check_headers(result, kind="spa", https=True), [])

    def test_backend_success_handled_errors_and_proxy_errors_keep_policies(self):
        for path, status in [("/api/health", 200), ("/api/missing", 404),
                             ("/api/failure", 500), ("/api/disconnect", 502), ("/api", 404)]:
            with self.subTest(path=path):
                result = self.get(path)
                self.assertEqual(result.status, status)
                self.assertEqual(check_headers(result, kind="api", https=True), [])

    def test_forwarding_headers_are_replaced_by_the_actual_edge_identity(self):
        result = self.get("/api/headers", headers={
            "X-Forwarded-For": "203.0.113.99", "X-Forwarded-Proto": "http",
            "Forwarded": "for=203.0.113.99;proto=http",
        })
        body = json.loads(result.body)
        self.assertEqual(body["forwarded_for"], "127.0.0.1")
        self.assertEqual(body["proto"], "https")
        self.assertIsNone(body["forwarded"])

    def test_http_redirect_preserves_path_and_never_emits_hsts(self):
        result = self.get("/about?source=check", tls=False, headers={"Host": "attacker.invalid"})
        self.assertEqual(result.status, 308)
        self.assertEqual(result.values("Location"), [self.base + "/about?source=check"])
        self.assertEqual(check_headers(result, kind="spa", https=False), [])

    def test_api_documentation_is_usable(self):
        for path in ["/docs", "/redoc", "/docs/oauth2-redirect"]:
            with self.subTest(path=path):
                result = self.get(path)
                self.assertEqual(result.status, 200)
                self.assertEqual(check_headers(result, kind="docs", https=True), [])

    def test_hidden_files_are_denied_with_headers(self):
        result = self.get("/.env")
        self.assertEqual(result.status, 403)
        self.assertNotIn(b"must not be served", result.body)
        self.assertEqual(check_headers(result, kind="spa", https=True), [])

    def test_deployment_checker_runs_all_read_only_probes(self):
        checks = check_site(self.base, context=self.context)
        self.assertEqual(len(checks), 9)
        self.assertTrue(all(item.ok for item in checks), checks)
        completed = subprocess.run([
            sys.executable, str(ROOT / "tools/check_deployment.py"), self.base,
            "--ca-file", str(self.cert), "--http-url", f"http://127.0.0.1:{self.http_port}",
        ], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(len(json.loads(completed.stdout)["checks"]), 10)


class CheckerInputTests(unittest.TestCase):
    def test_origin_rejects_credentials_paths_queries_and_wrong_scheme(self):
        for value in ["http://example.org", "https://user:pass@example.org", "https://example.org/path",
                      "https://example.org?token=abc", "https://example.org/#fragment", "https://example.org:99999"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                origin(value, "https")

    def test_origin_accepts_tls_loopback_and_normalizes_trailing_slash(self):
        self.assertEqual(origin("https://127.0.0.1:9443/", "https"), "https://127.0.0.1:9443")

    def test_duplicate_csp_directives_are_reported(self):
        with self.assertRaises(ValueError):
            policy("script-src 'self'; script-src *")

    def test_missing_and_duplicate_security_headers_are_failures(self):
        result = Response(200, [("X-Frame-Options", "DENY"), ("X-Frame-Options", "DENY")], b"")
        errors = check_headers(result, kind="spa", https=True)
        self.assertTrue(any("X-Frame-Options" in item for item in errors))
        self.assertTrue(any("Content-Security-Policy" in item for item in errors))
        self.assertTrue(any("HSTS" in item for item in errors))


class CheckerFailureTests(unittest.TestCase):
    def health_check(self, response):
        # Header policy is covered above. Isolate status, media type and body
        # checks here so a header failure cannot make a broken assertion pass.
        with patch("tools.check_deployment.request", return_value=response), \
             patch("tools.check_deployment.check_headers", side_effect=lambda *_a, **_kw: []):
            checks = check_site("https://example.org", context=ssl.create_default_context())
        return next(item for item in checks if item.path == "/api/health")

    def test_unexpected_status_is_a_failure_even_with_a_valid_body(self):
        response = Response(503, [("Content-Type", "application/json")], b'{"status":"ok"}')
        result = self.health_check(response)
        self.assertFalse(result.ok)
        self.assertIn("Expected HTTP 200, received 503", result.problems)

    def test_incorrect_content_types_are_rejected_including_prefix_matches(self):
        for content_type in ["text/html", "application/jsonp", "application/json-extra"]:
            with self.subTest(content_type=content_type):
                result = self.health_check(Response(200, [("Content-Type", content_type)], b'{"status":"ok"}'))
                self.assertFalse(result.ok)
                self.assertIn("Expected application/json content", result.problems)

    def test_content_type_parameters_and_case_are_accepted(self):
        result = self.health_check(Response(200, [("Content-Type", "Application/JSON; charset=utf-8")], b'{"status":"ok"}'))
        self.assertTrue(result.ok, result.problems)

    def test_malformed_and_non_object_health_json_are_reported(self):
        for body in [b"not json", b"\xff", b"[]", b"null", b"42", b'"ok"']:
            with self.subTest(body=body):
                result = self.health_check(Response(200, [("Content-Type", "application/json")], body))
                self.assertFalse(result.ok)
                self.assertIn("API health response was not a JSON object", result.problems)

    def test_health_object_must_report_ok(self):
        for body in [b"{}", b'{"status":"error"}', b'{"status":null}']:
            with self.subTest(body=body):
                result = self.health_check(Response(200, [("Content-Type", "application/json")], body))
                self.assertFalse(result.ok)
                self.assertIn("API health response did not report status ok", result.problems)

    def test_connection_and_tls_failures_hide_exception_details(self):
        secret = "private-token-and-host-details"
        for error in [OSError(secret), ssl.SSLError(secret), http.client.HTTPException(secret)]:
            with self.subTest(error=type(error).__name__), \
                 patch("tools.check_deployment.request", side_effect=error):
                checks = check_site("https://example.org", context=ssl.create_default_context())
                self.assertEqual(len(checks), 9)
                self.assertTrue(all(not item.ok for item in checks))
                self.assertTrue(all(item.problems == [f"Request failed: {type(error).__name__}"] for item in checks))
                self.assertNotIn(secret, str(checks))

    def test_invalid_timeouts_fail_before_any_requests(self):
        for timeout in ["0", "-1", "nan", "inf"]:
            with self.subTest(timeout=timeout), redirect_stderr(io.StringIO()), \
                 patch("tools.check_deployment.check_site") as check, \
                 self.assertRaises(SystemExit) as raised:
                main(["https://example.org", "--timeout", timeout])
            self.assertEqual(raised.exception.code, 2)
            check.assert_not_called()

    def test_wrong_redirect_status_or_destination_causes_failure(self):
        responses = [Response(200, [("Location", "https://example.org/about?header-check=1")], b""),
                     Response(308, [("Location", "https://wrong.example/about?header-check=1")], b"")]
        for response in responses:
            output = io.StringIO()
            with self.subTest(response=response), redirect_stdout(output), \
                 patch("tools.check_deployment.check_site", return_value=[Check("/", True, [])]), \
                 patch("tools.check_deployment.request", return_value=response), \
                 patch("tools.check_deployment.check_headers", return_value=[]):
                status = main(["https://example.org", "--http-url", "http://example.org"])
            self.assertEqual(status, 1)
            report = json.loads(output.getvalue())
            self.assertFalse(report["checks"][-1]["ok"])
            self.assertIn("HTTP must redirect", report["checks"][-1]["problems"][0])

    def test_failed_check_controls_cli_exit_status(self):
        output = io.StringIO()
        with redirect_stdout(output), patch("tools.check_deployment.check_site", return_value=[
            Check("/", True, []), Check("/api/health", False, ["fixture failure"]),
        ]):
            status = main(["https://example.org"])
        self.assertEqual(status, 1)
        self.assertFalse(json.loads(output.getvalue())["checks"][1]["ok"])


if __name__ == "__main__":
    unittest.main()
