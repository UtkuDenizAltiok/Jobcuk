import json
import time

import pytest
from conftest import FAKE_CV_LINES, make_pdf
from fastapi.testclient import TestClient

from jobcu import documents, search
from jobcu.ai.base import AIAuthError, ProviderAdapter, RawReply, Usage
from jobcu.app import create_app
from jobcu.settings import SearchForm, Settings, load_settings, save_settings

PROFILE = {
    "summary": "Hardware engineer.",
    "current_or_last_role": "Embedded Engineer",
    "field": "Electronics",
    "skills": ["PCB layout"],
    "technical_areas": ["Embedded systems"],
    "years_full_time_experience": 5,
    "years_student_or_part_time_experience": 0,
    "experience_note": "Five years.",
    "seniority": "mid",
    "education": [],
    "languages": [],
    "target_roles": ["Hardware Engineer"],
    "target_fields": ["Electronics"],
    "preferences": [],
    "work_mode_preference": "not_stated",
    "dealbreakers": [],
    "work_authorisation": None,
    "ignored_as_application_specific": [],
}
LOCATION = {
    "understood_as": "Jobs in Munich, Germany.",
    "limits_countries": True,
    "countries": ["DE"],
    "places": [
        {
            "name": "Munich",
            "local_name": "München",
            "country": "DE",
            "kind": "city",
            "radius_km": None,
        }
    ],
    "not_checked_yet": [],
    "outside_supported_area": [],
}
WORDS = {
    "terms": [
        {"text": "Hardware Engineer", "language": "en", "kind": "job_title"},
        {"text": "Hardwareentwickler", "language": "de", "kind": "job_title"},
    ]
}


class FakeAI(ProviderAdapter):
    """Answers each kind of request with made-up data."""

    def __init__(self):
        super().__init__("fake")

    def complete_json(self, **request):
        answer = {
            "Profile": PROFILE,
            "LocationUnderstanding": LOCATION,
            "SearchWordsAnswer": WORDS,
        }[request["schema_name"]]
        return RawReply(json.dumps(answer), Usage(10, 5))

    def list_models(self):
        return []


@pytest.fixture
def ready(monkeypatch):
    """Documents uploaded, AI chosen, and the fake AI plugged in."""
    documents.save_upload("cv", "cv.pdf", make_pdf(FAKE_CV_LINES))
    documents.save_upload("cover_letter", "letter.txt", b"I enjoy hardware design work. " * 5)
    settings = Settings()
    settings.ai.provider = "gemini"
    settings.ai.model = "model-a"
    save_settings(settings)
    monkeypatch.setattr("jobcu.ai.client.AIClient.adapter", lambda self: FakeAI())


def wait_until_done(manager, timeout=10):
    deadline = time.monotonic() + timeout
    while manager.current.status == "running" and time.monotonic() < deadline:
        time.sleep(0.02)
    return manager.current.snapshot()


def test_full_search_runs_all_steps(ready):
    manager = search.SearchManager()
    manager.start(SearchForm(location_text="Munich"))
    result = wait_until_done(manager)
    assert result["status"] == "finished", result["error"]
    steps = {s["id"]: s["status"] for s in result["steps"]}
    assert steps == {
        "documents": "done",
        "profile": "done",
        "location": "done",
        "search_words": "done",
        "sources": "skipped",
    }
    assert result["result"]["location"]["countries"] == ["DE"]
    assert [w["text"] for w in result["result"]["search_words"]] == [
        "Hardware Engineer",
        "Hardwareentwickler",
    ]
    assert result["result"]["usage"]["profile"]["input_tokens"] == 10


def test_missing_documents_stop_the_search_with_a_plain_message():
    manager = search.SearchManager()
    manager.start(SearchForm())
    result = wait_until_done(manager)
    assert result["status"] == "failed"
    assert result["error"] == "Please upload your CV first."
    assert result["steps"][0]["status"] == "failed"


def test_ai_problems_are_shown_plainly():
    def runner(run):
        run.update("documents", "running")
        raise AIAuthError("The AI provider didn't accept the key.")

    manager = search.SearchManager(runner=runner)
    manager.start(SearchForm())
    result = wait_until_done(manager)
    assert result["status"] == "failed" and "didn't accept the key" in result["error"]


def test_only_one_search_at_a_time_and_it_can_be_stopped():
    def slow_runner(run):
        run.update("documents", "running")
        while not run.stop_requested:
            time.sleep(0.01)
        raise search.SearchStopped

    manager = search.SearchManager(runner=slow_runner)
    run = manager.start(SearchForm())
    with pytest.raises(RuntimeError):
        manager.start(SearchForm())
    assert manager.stop(run.id)
    assert wait_until_done(manager)["status"] == "stopped"


def test_search_api_saves_the_form_and_reports_progress(ready, monkeypatch):
    manager = search.SearchManager()
    monkeypatch.setattr(search, "manager", manager)
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    body = {
        "location_text": "Munich",
        "posted_within_hours": 72,
        "job_types": ["full_time_permanent"],
        "exclude_remote": True,
    }
    started = client.post("/api/search", json=body, headers={"X-Jobcu": "1"}).json()
    assert started["status"] == "running"
    assert load_settings().search_form.posted_within_hours == 72
    wait_until_done(manager)
    current = client.get("/api/search/current").json()["search"]
    assert current["status"] == "finished"


def test_search_needs_a_job_type():
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    body = {"location_text": "", "posted_within_hours": 24, "job_types": []}
    response = client.post("/api/search", json=body, headers={"X-Jobcu": "1"})
    assert response.status_code == 400
