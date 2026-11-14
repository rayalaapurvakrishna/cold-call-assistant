import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from fastapi.testclient import TestClient

client = TestClient(main.app)


def setup_function():
    main.memory_calls.clear()


def test_health_does_not_require_external_services():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_call_can_be_saved_early_and_retrieved_with_exact_words():
    started = client.post('/calls', json={
        'prospect_name': 'Demo Prospect',
        'company_name': 'Example Manufacturing',
        'role': 'Operations Director',
    })
    assert started.status_code == 200
    call_id = started.json()['call']['id']

    stage = client.post(f'/calls/{call_id}/stage', json={
        'stage_number': 1,
        'stage_reached': 2,
        'actions': ['Confirmed the right person'],
        'prospect_words': 'Yes, speaking. What is this about?',
        'caller_note': 'Asked for context',
    })
    assert stage.status_code == 200

    closed = client.post(f'/calls/{call_id}/close', json={
        'outcome': 'follow_up',
        'final_note': 'Call after lunch',
        'prospect_words': 'Call me after lunch.',
        'actions': ['Asked for a callback'],
        'caller_note': 'Callback requested',
        'current_stage': 2,
        'stage_reached': 2,
    })
    assert closed.status_code == 200
    assert closed.json()['call']['stage_reached'] == 2

    detail = client.get(f'/calls/{call_id}')
    assert detail.status_code == 200
    assert len(detail.json()['stages']) == 2
    assert detail.json()['stages'][-1]['prospect_words'] == 'Call me after lunch.'


def test_revisiting_a_stage_updates_instead_of_duplicating():
    call_id = client.post('/calls', json={}).json()['call']['id']
    payload = {
        'stage_number': 3,
        'stage_reached': 3,
        'actions': ['Asked for a callback'],
        'prospect_words': 'Tomorrow afternoon.',
        'caller_note': '',
    }
    assert client.post(f'/calls/{call_id}/stage', json=payload).status_code == 200
    payload['prospect_words'] = 'Please call tomorrow after two.'
    assert client.post(f'/calls/{call_id}/stage', json=payload).status_code == 200
    detail = client.get(f'/calls/{call_id}').json()
    assert len(detail['stages']) == 1
    assert detail['stages'][0]['prospect_words'] == 'Please call tomorrow after two.'


def test_unknown_call_returns_404():
    response = client.get('/calls/00000000-0000-0000-0000-000000000000')
    assert response.status_code == 404


def test_ai_fails_gracefully_when_key_is_missing(monkeypatch):
    monkeypatch.setattr(main, 'GEMINI_API_KEY', '')
    response = client.post('/ai/suggest-stage', json={'stage_number': 3})
    assert response.status_code == 503


def test_furthest_stage_does_not_move_back_when_caller_edits_earlier_stage():
    call_id = client.post('/calls', json={}).json()['call']['id']
    for number in (1, 2, 3):
        response = client.post(f'/calls/{call_id}/stage', json={
            'stage_number': number,
            'stage_reached': number,
            'actions': [],
            'prospect_words': f'Stage {number}',
            'caller_note': '',
        })
        assert response.status_code == 200
    response = client.post(f'/calls/{call_id}/stage', json={
        'stage_number': 1,
        'stage_reached': 3,
        'actions': [],
        'prospect_words': 'Updated opening notes',
        'caller_note': '',
    })
    assert response.status_code == 200
    assert client.get(f'/calls/{call_id}').json()['call']['stage_reached'] == 3


def test_closing_while_viewing_earlier_stage_preserves_furthest_stage():
    call_id = client.post('/calls', json={}).json()['call']['id']
    response = client.post(f'/calls/{call_id}/close', json={
        'outcome': 'follow_up',
        'final_note': 'Callback agreed',
        'prospect_words': 'Please call me Friday.',
        'actions': ['Asked for a callback'],
        'caller_note': 'Exact time to confirm',
        'current_stage': 2,
        'stage_reached': 6,
    })
    assert response.status_code == 200
    detail = client.get(f'/calls/{call_id}').json()
    assert detail['call']['stage_reached'] == 6
    assert detail['stages'][0]['stage_number'] == 2
    assert detail['stages'][0]['prospect_words'] == 'Please call me Friday.'


def test_start_call_rejects_oversized_company_name():
    response = client.post("/calls", json={
        "company_name": "A" * 501
    })
    assert response.status_code == 422


def test_memory_history_includes_active_calls():
    response = client.post("/calls", json={
        "prospect_name": "Test Prospect"
    })
    assert response.status_code == 200

    history = client.get("/calls")
    assert history.status_code == 200
    assert any(
        call["id"] == response.json()["call"]["id"]
        for call in history.json()["calls"]
    )


def test_stage_save_rejects_more_than_twenty_actions():
    call_id = client.post("/calls", json={}).json()["call"]["id"]

    response = client.post(f"/calls/{call_id}/stage", json={
        "stage_number": 1,
        "stage_reached": 1,
        "actions": ["Action"] * 21
    })

    assert response.status_code == 422

