"""Document the public error contract without waiting for the real timeout."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import claims
from app.services import research_overview as overview
from tests.test_claims import api, calls, cache
from tests.test_research_overview import clean_overview_caches, fake_generator


def test_openapi_documents_overview_recovery_responses():
    schema = TestClient(app).get('/openapi.json').json()
    operation = schema['paths']['/api/claims/overview/{analysis_id}']['post']
    responses = operation['responses']
    assert {'200', '410', '503'} <= responses.keys()
    assert 'refresh' in responses['410']['description'].lower()
    assert 'retry' in responses['503']['description'].lower()
    assert 'studies' in responses['503']['description'].lower()
    success = responses['200']['content']['application/json']['schema']
    assert success['$ref'].endswith('/ResearchOverview')
    assert operation['parameters'][0]['name'] == 'analysis_id'


@pytest.mark.parametrize('token', ['unknown', 'baseline-expired-token'])
def test_unknown_snapshot_returns_documented_410_without_starting_work(token, monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail('An expired token must not start overview generation')
    monkeypatch.setattr(claims, 'shared_overview', forbidden)
    response = TestClient(app).post('/api/claims/overview/' + token)
    assert response.status_code == 410
    assert response.json() == {'detail': 'Search snapshot expired. Refresh the search.'}


def test_timeout_returns_503_and_preserves_the_snapshot_for_retry(api, monkeypatch):
    client = api()
    search = client.post('/api/claims', json={'claim': 'Does zinc prevent colds?', 'limit': 3})
    assert search.status_code == 200
    token = search.json()['analysis_id']
    snapshot = overview.snapshots.get(token).model_copy(deep=True)
    path = '/api/claims/overview/' + token
    original = claims.shared_overview
    async def timeout(*args, **kwargs):
        raise TimeoutError
    monkeypatch.setattr(claims, 'shared_overview', timeout)
    response = client.post(path)
    assert response.status_code == 503
    assert response.json() == {
        'detail': 'Overview took too long. Retry; your studies are still available.',
    }
    assert overview.snapshots.get(token) == snapshot
    monkeypatch.setattr(claims, 'shared_overview', original)
    monkeypatch.setattr(overview, 'generate', fake_generator([]))
    retried = client.post(path)
    assert retried.status_code == 200
    assert retried.json()['coverage']['analyzed'] == 3


def test_expired_snapshot_is_not_restored_by_retry(api):
    client = api()
    found = client.post('/api/claims', json={'claim': 'Does zinc prevent colds?'}).json()
    overview.snapshots.clear()
    path = '/api/claims/overview/' + found['analysis_id']
    assert client.post(path).status_code == 410
    assert client.post(path).status_code == 410
    refreshed = client.post('/api/claims', json={'claim': 'Does zinc prevent colds?'}).json()
    assert refreshed['analysis_id'] != found['analysis_id']
    assert overview.snapshots.get(refreshed['analysis_id']) is not None
