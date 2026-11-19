"""Optional same-origin hosting for the production React build."""

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class FrontendFiles(StaticFiles):
    def __init__(self, directory: Path) -> None:
        super().__init__(directory=directory, html=True)
        if not (directory / "index.html").is_file():
            raise RuntimeError("FRONTEND_DIST must contain a built index.html")

    async def get_response(self, path: str, scope: Scope):
        # Missing API routes must remain JSON 404s, never the SPA document.
        if path.split("/", 1)[0] in {"api", "docs", "redoc", "openapi.json"}:
            raise HTTPException(status_code=404)
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            # Only browser document requests use client-side routing. Missing
            # JS, fonts, images, etc. retain their actual 404 response.
            accepts_html = any(
                name == b"accept" and b"text/html" in value
                for name, value in scope["headers"]
            )
            if not accepts_html or Path(path).suffix:
                raise
            response = await super().get_response("index.html", scope)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        return response
