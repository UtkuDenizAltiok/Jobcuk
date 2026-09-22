import pytest
from fastapi.testclient import TestClient

from jobcu.app import create_app
from jobcu.keystore import KeyStore
from jobcu.settings import load_settings

HEADERS = {"X-Jobcu": "1"}


@pytest.fixture
def client():
    return TestClient(create_app(), base_url="http://127.0.0.1:8765")


def test_settings_list_providers_alphabetically_with_no_default(client):
    data = client.get("/api/settings").json()
    names = [p["name"] for p in data["providers"]]
    assert names == sorted(names[:-1]) + ["Other (OpenAI-compatible)"]
    assert data["ai"]["provider"] is None
    assert all(not p["key"]["saved"] for p in data["providers"])


def test_keys_are_saved_masked_and_removed(client):
    value = "fake-" + "k" * 20 + "wxyz"
    saved = client.put("/api/keys/reed_api_key", json={"value": value}, headers=HEADERS).json()
    assert saved == {"name": "reed_api_key", "saved": True, "hint": "••••wxyz"}
    assert KeyStore().get("reed_api_key") == value
    assert value not in client.get("/api/settings").text
    client.delete("/api/keys/reed_api_key", headers=HEADERS)
    assert KeyStore().get("reed_api_key") is None


def test_unknown_key_names_are_refused(client):
    response = client.put("/api/keys/anything", json={"value": "x" * 20}, headers=HEADERS)
    assert response.status_code == 404


def test_ai_choice_is_saved(client):
    body = {"provider": "openai", "model": " some-model ", "reasoning_model": "", "base_url": ""}
    data = client.put("/api/settings/ai", json=body, headers=HEADERS).json()
    assert data["ai"]["model"] == "some-model"
    assert load_settings().ai.provider == "openai"


def test_model_list_needs_a_saved_key(client):
    data = client.post("/api/ai/models", json={"provider": "anthropic"}, headers=HEADERS).json()
    assert data["models"] == [] and "save your key" in data["error"]


def test_job_site_check_without_keys_explains_what_to_do(client):
    data = client.post("/api/job-sites/adzuna/check", headers=HEADERS).json()
    assert not data["ok"]
    assert data["message"] == "Please save both the Application ID and the Application Key."


def test_unknown_job_site_is_refused(client):
    assert client.post("/api/job-sites/nowhere/check", headers=HEADERS).status_code == 404


def test_usage_shows_the_month_the_last_search_and_the_sources(client):
    from datetime import UTC, datetime

    from jobcu import db
    from jobcu.ai.base import Usage
    from jobcu.ai.usage import UsageLog

    with db.connect() as conn:
        conn.execute("INSERT INTO searches (id, status, form_json) VALUES (7, 'finished', '{}')")
        conn.execute(
            "INSERT INTO source_requests (day, source, count) VALUES (?, 'adzuna', 12)",
            (datetime.now(UTC).strftime("%Y-%m-%d"),),
        )
    UsageLog().record(step="scoring", provider="openai", model="a-model",
                      usage=Usage(input_tokens=1_000_000, output_tokens=500_000), search_id=7)

    data = client.get("/api/usage", headers=HEADERS).json()
    assert data["this_month"]["tokens"] == 1_500_000
    assert data["this_month"]["cost_is_complete"] is False  # no prices saved yet
    assert data["last_search"]["tokens"] == 1_500_000
    adzuna = next(s for s in data["sources"] if s["id"] == "adzuna")
    assert adzuna["requests_today"] == 12 and adzuna["enabled"]
    assert {s["id"] for s in data["sources"]} >= {"jobsireland", "workday", "arbeitnow"}

    # The user's own price table turns tokens into money.
    prices = [{"provider": "openai", "model": "a-model", "input_per_million": 2,
               "output_per_million": 8, "currency": "EUR"}]
    data = client.put("/api/settings/prices", json={"prices": prices}, headers=HEADERS).json()
    assert data["this_month"]["cost"] == 6.0 and data["this_month"]["cost_is_complete"]
    assert data["last_search"]["cost"] == 6.0 and data["this_month"]["currency"] == "EUR"


def test_limits_and_source_switches_are_saved(client):
    data = client.put("/api/settings/limits", headers=HEADERS, json={
        "scoring_cap": 40, "monthly_token_limit": 2_000_000, "monthly_cost_limit": 25.0,
    }).json()
    assert data["limits"]["scoring_cap"] == 40
    assert data["limits"]["monthly_token_limit"] == 2_000_000
    assert data["limits"]["web_search_cap"] == 50  # not sent: kept as it was
    data = client.put("/api/settings/limits", headers=HEADERS, json={
        "scoring_cap": 40, "web_search_cap": 20}).json()
    assert data["limits"]["web_search_cap"] == 20 and load_settings().limits.web_search_cap == 20

    data = client.put("/api/settings/sources", headers=HEADERS,
                      json={"disabled": ["workday", "not-a-source"]}).json()
    switched_off = {s["id"] for s in data["sources"] if not s["enabled"]}
    assert switched_off == {"workday"}
    assert load_settings().sources_disabled == ["workday"]
