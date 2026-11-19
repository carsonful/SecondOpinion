"""Browser hardening for API responses without changing JSON error contracts."""

from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = (
                    "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
                )
                # JSON API responses need no scripts, styles, or subresources.
                # Swagger/ReDoc are HTML documents with separate asset needs.
                path = scope.get("path", "")
                if path == "/api" or path.startswith("/api/") or path == "/openapi.json":
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; frame-ancestors 'none'; "
                        "base-uri 'none'; form-action 'none'"
                    )
                # Trust ASGI's scheme, never a raw X-Forwarded-Proto header.
                if scope.get("scheme") == "https":
                    headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class SecurityHeadersFastAPI(FastAPI):
    def build_middleware_stack(self) -> ASGIApp:
        # Wrap ServerErrorMiddleware too, so unexpected 500s receive the same
        # policies as handled errors, CORS preflights, and successful responses.
        return SecurityHeadersMiddleware(super().build_middleware_stack())
