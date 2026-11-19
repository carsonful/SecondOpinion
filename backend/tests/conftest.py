import pytest


@pytest.fixture(autouse=True)
def disable_shared_app_request_limit(monkeypatch):
    # Existing functional tests share the module-level app. Limiter integration
    # tests construct a fresh app with an explicitly enabled budget.
    from app.main import app

    monkeypatch.setattr(app.state.inference_limiter, "enabled", False)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
