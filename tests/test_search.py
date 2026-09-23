import json
import re
import time
from datetime import UTC, datetime

import pytest
from conftest import FAKE_CV_LINES, make_pdf
from fastapi.testclient import TestClient

from jobcu import documents, jobstore, search
from jobcu.ai.base import AIAuthError, ProviderAdapter, RawReply, Usage
from jobcu.app import create_app
from jobcu.settings import SearchForm, Settings, load_settings, save_settings
from jobcu.sources.base import FoundJob, JobSource

HEADERS = {"X-Jobcu": "1"}
PROFILE = {
    "summary": "Hardware engineer.", "current_or_last_role": "Embedded Engineer",
    "field": "Electronics", "skills": ["PCB layout"], "technical_areas": ["Embedded systems"],
    "years_full_time_experience": 5, "years_student_or_part_time_experience": 0,
    "experience_note": "Five years.", "seniority": "mid", "education": [], "languages": [],
    "target_roles": ["Hardware Engineer"], "target_fields": ["Electronics"], "preferences": [],
    "work_mode_preference": "not_stated", "dealbreakers": [], "work_authorisation": None,
    "ignored_as_application_specific": [],
}
LOCATION = {
    "understood_as": "Jobs in Germany.", "limits_countries": True, "countries": ["DE"],
    "places": [], "conditions_about_places": [], "conditions_about_the_job": [],
    "outside_supported_area": [],
}
WORDS = {"terms": [{"text": "Hardware Engineer", "language": "en", "kind": "job_title"}]}


class FakeAI(ProviderAdapter):
    """Answers each kind of request with made-up data."""

    def __init__(self):
        super().__init__("fake")

    def complete_json(self, **request):
        name, prompt = request["schema_name"], request["prompt"]
        if name == "QuickPassAnswer":
            ids = re.findall(r"^(J\d+) \| Nurse", prompt, re.MULTILINE)
            answer = {"clearly_unrelated": ids, "places": []}
        elif name == "ScoringAnswer":
            answer = {"scores": [
                {"job_id": job_id, "ad_language": "English", "languages_asked": [],
                 "years_required": None, "doctorate": "not_required",
                 "citizenship_or_clearance": "no_such_requirement",
                 "citizenship_or_clearance_words": "", "role_and_skills": 35, "seniority": 18,
                 "hard_requirements": 15, "location_and_preferences": 9,
                 "reasons": ["Strong match"], "job_type": "full_time_permanent",
                 "work_mode": "on_site", "fully_remote": False}
                for job_id in re.findall(r"^JOB (J\d+)", prompt, re.MULTILINE)
            ]}
        else:
            answer = {"Profile": PROFILE, "LocationUnderstanding": LOCATION,
                      "SearchWordsAnswer": WORDS}[name]
        return RawReply(json.dumps(answer), Usage(10, 5))

    def list_models(self):
        return []


class FakeSource(JobSource):
    id = "fake"
    name = "Fake Jobs"
    kind = "job_board"
    titles = ["Hardware Engineer", "Electronics Engineer", "Nurse"]

    def search(self, query, ctx):
        for i, title in enumerate(self.titles):
            ctx.report.requests += 1
            yield FoundJob(source="fake", source_job_id=str(i), url=f"https://jobs.test/{i}",
                           title=title, company=f"Company {i}", location_text="Berlin",
                           country="DE", posted_at=datetime.now(UTC), date_precision="exact",
                           description="Short")

    def load_details(self, job, ctx):
        job.description, job.description_is_complete = "Full ad text", True
        return job


@pytest.fixture
def ready(monkeypatch):
    """Documents uploaded, AI chosen, the fake AI and the fake job source plugged in."""
    documents.save_upload("cv", "cv.pdf", make_pdf(FAKE_CV_LINES))
    documents.save_upload("cover_letter", "letter.txt", b"I enjoy hardware design work. " * 5)
    settings = Settings()
    settings.ai.provider = "gemini"
    settings.ai.model = "model-a"
    save_settings(settings)
    monkeypatch.setattr("jobcu.ai.client.AIClient.adapter", lambda self: FakeAI())
    monkeypatch.setattr("jobcu.pipeline.all_sources", lambda: [FakeSource()])


def wait_until_done(manager, answer=None, timeout=15):
    deadline = time.monotonic() + timeout
    while manager.current.status == "running" and time.monotonic() < deadline:
        if answer is not None and manager.current.question:
            manager.current.answer(answer)
        time.sleep(0.02)
    return manager.current.snapshot()


def test_full_search_finds_filters_scores_and_remembers(ready):
    manager = search.SearchManager()
    manager.start(SearchForm(location_text="Germany"))
    result = wait_until_done(manager)
    assert result["status"] == "finished", result["error"]
    assert all(step["status"] == "done" for step in result["steps"])
    jobs = result["result"]["jobs"]
    titles = [card["title"] for card in jobs["cards"]]
    assert sorted(titles) == ["Electronics Engineer", "Hardware Engineer"]
    assert jobs["counts"]["unrelated"] == 1 and jobs["counts"]["unrelated_titles"] == ["Nurse"]
    card = jobs["cards"][0]
    assert card["score"] == 92 and card["is_new"] and not card["summary_only"]
    assert card["location_checks"][0]["status"] == "verified"
    assert jobs["sources"][0]["unique"] == 2 and jobs["new_count"] == 2

    # The next search recognises the same jobs: no "New" badge.
    manager.start(SearchForm(location_text="Germany"))
    again = wait_until_done(manager)["result"]["jobs"]
    assert again["new_count"] == 0


def test_not_interested_jobs_are_hidden_from_later_searches(ready):
    manager = search.SearchManager()
    manager.start(SearchForm())
    first = wait_until_done(manager)["result"]["jobs"]["cards"]
    jobstore.set_state(first[0]["job_id"], dismissed=True)
    manager.start(SearchForm())
    jobs = wait_until_done(manager)["result"]["jobs"]
    assert len(jobs["cards"]) == 1
    assert [c["title"] for c in jobs["hidden"]] == [first[0]["title"]]


@pytest.mark.parametrize(("answer", "scored"), [(False, 1), (True, 2)])
def test_scoring_limit_asks_before_doing_more(ready, answer, scored):
    settings = load_settings()
    settings.limits.scoring_cap = 1
    save_settings(settings)
    manager = search.SearchManager()
    manager.start(SearchForm())
    result = wait_until_done(manager, answer=answer)
    cards = result["result"]["jobs"]["cards"]
    assert sum(1 for c in cards if c["score"] is not None) == scored
    assert len(cards) == 2  # unscored jobs are still shown, never silently dropped


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


def test_search_api_job_states_and_results_after_a_restart(ready, monkeypatch):
    manager = search.SearchManager()
    monkeypatch.setattr(search, "manager", manager)
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    body = {"location_text": "Germany", "posted_within_hours": 72,
            "job_types": ["full_time_permanent"], "exclude_remote": True}
    assert client.post("/api/search", json=body, headers=HEADERS).json()["status"] == "running"
    assert load_settings().search_form.posted_within_hours == 72
    wait_until_done(manager)
    card = client.get("/api/search/current").json()["search"]["result"]["jobs"]["cards"][0]

    changed = client.post(f"/api/jobs/{card['job_id']}/state", json={"saved": True},
                          headers=HEADERS).json()
    assert changed["state"]["saved"]
    saved = client.get("/api/jobs/marked/saved").json()["cards"]
    assert [c["job_id"] for c in saved] == [card["job_id"]]

    # After a restart there is no running search, but the last results are still shown,
    # with up-to-date job states.
    monkeypatch.setattr(search, "manager", search.SearchManager())
    restored = client.get("/api/search/current").json()["search"]
    restored_card = next(c for c in restored["result"]["jobs"]["cards"]
                         if c["job_id"] == card["job_id"])
    assert restored["status"] == "finished" and restored_card["state"]["saved"]


def test_search_needs_a_job_type():
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    body = {"location_text": "", "posted_within_hours": 24, "job_types": []}
    assert client.post("/api/search", json=body, headers=HEADERS).status_code == 400


def test_unknown_job_state_is_refused():
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    response = client.post("/api/jobs/999/state", json={"saved": True}, headers=HEADERS)
    assert response.status_code == 404
