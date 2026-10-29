"""Population survives API serialization, persisted caches, and both model stages."""

import asyncio
import hashlib
import json

import httpx2 as httpx
import pytest

from app.models.claims import ClaimCandidates
from app.models.metadata import StudyPopulation
from app.services import durable_cache, research_overview as service
from app.services.pubmed import parse_efetch_xml
from tests.helpers import load_fixture, esearch_response
from tests.test_claims import api, calls, cache
from tests.test_research_overview import fake_generator, clean_overview_caches


@pytest.fixture
def result(api):
    response = api().post('/api/claims', json={'claim': 'Does zinc prevent colds?', 'limit': 3})
    assert response.status_code == 200
    return ClaimCandidates.model_validate(response.json())


def test_api_includes_population_on_fresh_and_cached_results(api, calls):
    client = api()
    first = client.post('/api/claims', json={'claim': 'Does zinc prevent colds?', 'limit': 3})
    before = calls.external
    second = client.post('/api/claims', json={'claim': 'Does zinc prevent colds?', 'limit': 3})
    assert first.status_code == second.status_code == 200
    assert second.json()['cached'] is True
    assert before == calls.external
    assert first.json()['candidates'][0]['metadata']['population'] == 'human'
    assert [c['metadata'] for c in first.json()['candidates']] == [
        c['metadata'] for c in second.json()['candidates']
    ]


def test_recorded_animal_metadata_reaches_the_api(api, calls):
    (animal,) = parse_efetch_xml(load_fixture('pubmed/efetch_animal_trial.xml'))
    client = api()
    calls.ncbi.esearch = lambda _: esearch_response([animal.pmid])
    calls.ncbi.efetch = lambda _: httpx.Response(
        200, content=load_fixture('pubmed/efetch_animal_trial.xml'),
    )
    response = client.post('/api/claims', json={'claim': 'Does treatment improve wound healing?'})
    assert response.status_code == 200
    study = response.json()['candidates'][0]
    assert study['article']['pmid'] == animal.pmid
    assert study['metadata'] == {'design': 'randomized_controlled_trial', 'population': 'animal'}


@pytest.mark.parametrize('population', list(StudyPopulation))
def test_both_generation_stages_receive_population(result, monkeypatch, population):
    for candidate in result.candidates:
        candidate.metadata.population = population
    recorded = []
    base = fake_generator(recorded)
    prompts = []
    async def generate(client, schema, prompt, data):
        prompts.append(prompt)
        return await base(client, schema, prompt, data)
    monkeypatch.setattr(service, 'generate', generate)
    output = asyncio.run(service.build_overview(result))
    assert output.status == 'complete'
    readings = recorded[:-1]
    assert len(readings) == 3
    assert all(data['population'] == population for data in readings)
    assert recorded[-1]['populations'] == {
        c.article.pmid: population for c in result.candidates
    }
    assert all('animal' in prompt and 'human' in prompt for prompt in prompts)
    assert 'Unknown does not mean' in prompts[-1]


def test_population_change_invalidates_reading_and_synthesis(result, monkeypatch):
    recorded = []
    monkeypatch.setattr(service, 'generate', fake_generator(recorded))
    original_key = service.cache_key(result)
    asyncio.run(service.build_overview(result))
    result.candidates[0].metadata.population = StudyPopulation.ANIMAL
    assert service.cache_key(result) != original_key
    asyncio.run(service.build_overview(result))
    # Only the changed study is reread, plus a fresh synthesis.
    assert len(recorded) == 6
    assert recorded[-2]['population'] == 'animal'
    assert recorded[-1]['populations'][result.candidates[0].article.pmid] == 'animal'


def test_version_change_invalidates_all_readings(result, monkeypatch):
    recorded = []
    monkeypatch.setattr(service, 'generate', fake_generator(recorded))
    old_key = service.cache_key(result)
    asyncio.run(service.build_overview(result))
    monkeypatch.setattr(service, 'VERSION', 'future-population-version')
    assert service.cache_key(result) != old_key
    asyncio.run(service.build_overview(result))
    assert len(recorded) == 8


def test_withheld_and_missing_abstracts_do_not_enter_population_mapping(result, monkeypatch):
    result.candidates[0].integrity.status = 'corrected'
    result.candidates[1].article.abstract = None
    recorded = []
    monkeypatch.setattr(service, 'generate', fake_generator(recorded))
    asyncio.run(service.build_overview(result))
    assert set(recorded[-1]['populations']) == {result.candidates[2].article.pmid}


def test_persistent_key_cannot_hit_pre_population_payload():
    old = hashlib.sha256(json.dumps(
        [2, 'candidates', '(zinc) AND (common cold)', 20],
        ensure_ascii=False, separators=(',', ':'),
    ).encode()).hexdigest()
    assert durable_cache.FORMAT_VERSION == 3
    assert durable_cache.cache_key('candidates', '(zinc) AND (common cold)', 20) != old


@pytest.mark.anyio
async def test_population_round_trips_through_persistent_serialization(result, monkeypatch):
    from pydantic import SecretStr
    store = durable_cache.PostgresClaimsCache(SecretStr('postgresql://unused/test'), 3600)
    result.candidates[0].metadata.population = StudyPopulation.ANIMAL
    written = {}
    async def put(layer, key, payload):
        written[(layer, key)] = json.loads(json.dumps(payload))
    async def get(layer, key):
        return written.get((layer, key))
    monkeypatch.setattr(store, '_put', put)
    monkeypatch.setattr(store, '_get', get)
    await store.put_candidates(result.normalized.query, 3, result)
    loaded = await store.get_candidates(result.normalized.query, 3)
    assert loaded.candidates[0].metadata.population == 'animal'
    assert loaded.candidates[0].metadata.design == result.candidates[0].metadata.design
