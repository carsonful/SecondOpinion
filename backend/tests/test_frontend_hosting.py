"""Production document routing must not swallow API or asset errors."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Settings


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text('<html><div id="root"></div></html>')
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('app')")
    settings = Settings(
        _env_file=None, frontend_dist=tmp_path,
        database_url=None, cache_database_url=None,
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    return TestClient(main.create_app())


@pytest.mark.parametrize("path", ["/", "/about", "/how-it-works", "/unknown-page"])
def test_documents_support_refresh_and_frontend_not_found(hosted, path):
    response = hosted.get(path, headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert 'id="root"' in response.text
    assert response.headers["Cache-Control"] == "no-cache"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"
    assert hosted.head(path, headers={"Accept": "text/html"}).content == b""


@pytest.mark.parametrize("path", ["/api", "/api/missing", "/assets/missing.js", "/missing.woff2"])
def test_missing_api_and_assets_do_not_return_html(hosted, path):
    response = hosted.get(path, headers={"Accept": "text/html"})
    assert response.status_code == 404
    assert 'id="root"' not in response.text


def test_static_assets_and_api_routes_remain_accessible(hosted):
    assert hosted.get("/assets/app.js").text == "console.log('app')"
    response = hosted.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert hosted.get("/openapi.json").json()["info"]["title"] == "SecondOpinion API"
    assert "Content-Security-Policy" not in hosted.get("/docs").headers
    assert hosted.post("/about").status_code == 405


def test_invalid_frontend_build_fails_at_startup(tmp_path):
    from app.frontend import FrontendFiles

    with pytest.raises(RuntimeError, match="index.html"):
        FrontendFiles(tmp_path)
