import asyncio
import json

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.models.claims import ClaimCandidates
from app.models.overview import StudyExplanation, Synthesis
from app.services import research_overview as service
from tests.test_claims import api, calls, cache  # reuse the recorded search fixtures


@pytest.fixture(autouse=True)
def clean_overview_caches():
    service.read_cache.clear()
    service.completed.clear()
    service.snapshots.clear()
    yield
    service.read_cache.clear()
    service.completed.clear()
    service.snapshots.clear()


@pytest.fixture
def result(api):
    response = api().post('/api/claims', json={'claim': 'Does zinc prevent colds?', 'limit': 3})
    assert response.status_code == 200
    return ClaimCandidates.model_validate(response.json())


def explanation(abstract, relevance='direct'):
    return StudyExplanation(
        summary={'text': 'The authors report findings.', 'passage': abstract[:100]},
        relevance=relevance,
        relationship={'text': 'This examines the question.', 'passage': abstract[:100]},
        gaps=['Participant details are not reported in the abstract.'],
    )


def fake_generator(calls):
    async def generate(client, schema, prompt, data):
        calls.append(data)
        if schema is StudyExplanation:
            return explanation(data['abstract'])
        return Synthesis(observations=[{'text': 'The retrieved abstracts report findings.',
                                       'pmids': [data['readings'][0]['pmid']]}], qualifications=[])
    return generate


def test_two_stages_exact_claim_and_cache(result, monkeypatch):
    calls = []
    monkeypatch.setattr(service, 'generate', fake_generator(calls))
    first = asyncio.run(service.build_overview(result))
    assert first.coverage.analyzed == 3
    assert first.coverage.direct == 3
    assert all(c['claim'] == result.claim for c in calls)
    assert 'passage' in calls[-1]['readings'][0]['explanation']['summary']
    second = asyncio.run(service.build_overview(result))
    assert second.cached
    assert len(calls) == 4
    opposite = result.model_copy(update={'claim': 'Zinc does not prevent colds'})
    assert service.cache_key(opposite) != service.cache_key(result)
    altered = result.model_copy(deep=True)
    altered.candidates[0].integrity.status = 'corrected'
    assert service.cache_key(altered) != service.cache_key(result)
    altered.candidates[0].article.abstract = 'Changed source'
    assert service.cache_key(altered) != service.cache_key(result)


def test_gaps_and_integrity_skip_model(result, monkeypatch):
    result.candidates[0].article.abstract = None
    result.candidates[1].integrity.status = 'expression_of_concern'
    result.candidates[2].integrity.status = 'corrected'
    async def forbidden(*args):
        raise AssertionError('No model calls expected')
    monkeypatch.setattr(service, 'generate', forbidden)
    overview = asyncio.run(service.build_overview(result))
    assert overview.status == 'insufficient_information'
    assert overview.coverage.no_abstract == 1
    assert overview.coverage.withheld == 2
    assert overview.synthesis is None


def test_fabricated_passages_withheld_and_partial_recoverable(result, monkeypatch):
    calls = []
    good = fake_generator(calls)
    bad_abstract = result.candidates[0].article.abstract
    async def generate(client, schema, prompt, data):
        output = await good(client, schema, prompt, data)
        if schema is StudyExplanation and data['abstract'] == bad_abstract:
            output.summary.passage = 'Fabricated quote not in the abstract.'
        return output
    monkeypatch.setattr(service, 'generate', generate)
    overview = asyncio.run(service.build_overview(result))
    assert overview.status == 'partial'
    assert overview.coverage.failed == 1
    assert len(calls[-1]['readings']) == 2
    assert service.completed.get(service.cache_key(result)) is None


def test_unknown_synthesis_citation_rejected(result, monkeypatch):
    good = fake_generator([])
    async def generate(client, schema, prompt, data):
        output = await good(client, schema, prompt, data)
        if schema is Synthesis:
            output.observations[0].pmids = ['999999999']
        return output
    monkeypatch.setattr(service, 'generate', generate)
    overview = asyncio.run(service.build_overview(result))
    assert overview.status == 'unavailable'
    assert overview.synthesis is None
    assert overview.coverage.analyzed == 3


def test_provider_failure_preserves_readings(result, monkeypatch):
    async def failure(*args):
        raise service.OverviewUnavailable('provider unavailable')
    monkeypatch.setattr(service, 'generate', failure)
    overview = asyncio.run(service.build_overview(result))
    assert overview.status == 'unavailable'
    assert overview.coverage.failed == 3
    assert service.completed.get(service.cache_key(result)) is None


def test_snapshot_route_and_expiry(result, monkeypatch):
    monkeypatch.setattr(service, 'generate', fake_generator([]))
    client = TestClient(app)
    response = client.post('/api/claims/overview/' + result.analysis_id)
    assert response.status_code == 200
    assert response.json()['coverage']['analyzed'] == 3
    service.snapshots.clear()
    assert client.post('/api/claims/overview/' + result.analysis_id).status_code == 410


def test_snapshot_is_immutable_copy(result):
    token = service.register_snapshot(result)
    result.claim = 'tampered'
    assert service.snapshots.get(token).claim != 'tampered'


def test_http_generation_validates_and_sanitizes(monkeypatch):
    monkeypatch.setattr(service, 'get_settings', lambda: Settings(
        _env_file=None, azure_inference_endpoint='https://example.org',
        azure_model_deployment_name='test', azure_inference_api_key='test-secret',
    ))
    async def run(status, body):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))) as client:
            return await service.generate(client, StudyExplanation, 'prompt', {'claim': 'test'})
    payload = {'choices': [{'finish_reason': 'stop', 'message': {'content': explanation('Source passage.').model_dump_json()}}]}
    assert asyncio.run(run(200, payload)).relevance == 'direct'
    with pytest.raises(service.OverviewUnavailable, match='validated'):
        asyncio.run(run(401, {'secret': 'private provider error'}))
    payload['choices'][0]['finish_reason'] = 'length'
    with pytest.raises(service.OverviewUnavailable):
        asyncio.run(run(200, payload))


def test_concurrent_overviews_share_work(result, monkeypatch):
    calls = []
    monkeypatch.setattr(service, 'generate', fake_generator(calls))
    async def concurrent():
        return await asyncio.gather(service.shared_overview(result), service.shared_overview(result))
    outputs = asyncio.run(concurrent())
    assert outputs[0] == outputs[1]
    assert len(calls) == 4


def test_retry_reuses_valid_readings(result, monkeypatch):
    calls = []
    good = fake_generator(calls)
    async def fail_synthesis(client, schema, prompt, data):
        if schema is Synthesis:
            raise service.OverviewUnavailable('temporary error')
        return await good(client, schema, prompt, data)
    monkeypatch.setattr(service, 'generate', fail_synthesis)
    assert asyncio.run(service.build_overview(result)).status == 'unavailable'
    monkeypatch.setattr(service, 'generate', good)
    assert asyncio.run(service.build_overview(result)).status == 'complete'
    assert len(calls) == 4


def test_coverage_separates_relevance_from_agreement(result, monkeypatch):
    calls = []
    good = fake_generator(calls)
    categories = iter(['related', 'not_addressed', 'unclear'])
    async def generate(client, schema, prompt, data):
        output = await good(client, schema, prompt, data)
        if schema is StudyExplanation:
            output.relevance = next(categories)
        return output
    monkeypatch.setattr(service, 'generate', generate)
    overview = asyncio.run(service.build_overview(result))
    assert overview.coverage.direct == 0
    assert overview.coverage.related == overview.coverage.not_addressed == overview.coverage.unclear == 1


def test_twenty_paper_bound_and_retractions(result, monkeypatch):
    prototype = result.candidates[0]
    result.candidates = []
    for index in range(21):
        candidate = prototype.model_copy(deep=True)
        candidate.article.pmid = str(index + 1)
        result.candidates.append(candidate)
    result.excluded_retracted = [prototype]
    calls = []
    monkeypatch.setattr(service, 'generate', fake_generator(calls))
    overview = asyncio.run(service.build_overview(result))
    assert overview.coverage.analyzed == 20
    assert overview.coverage.outside_limit == 1
    assert overview.coverage.excluded_retracted == 1
    assert len(calls[-1]['readings']) == 20
    assert all(r['pmid'] != prototype.article.pmid for r in calls[-1]['readings'])
