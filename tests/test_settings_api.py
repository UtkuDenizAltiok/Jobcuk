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
