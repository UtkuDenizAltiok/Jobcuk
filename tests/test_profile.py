import json

import pytest
from conftest import FAKE_CV_LINES, make_pdf
from fastapi.testclient import TestClient

from jobcu import documents
from jobcu.ai.base import ProviderAdapter, RawReply, Usage
from jobcu.ai.client import AIClient
from jobcu.app import create_app
from jobcu.profile import Profile, read_profile, read_profile_reusing
from jobcu.settings import Settings

PROFILE = {
    "summary": "An embedded hardware engineer looking for hardware design roles.",
    "current_or_last_role": "Embedded Engineer",
    "field": "Electronics",
    "skills": ["PCB layout"],
    "technical_areas": ["Embedded systems"],
    "years_full_time_experience": 5,
    "years_student_or_part_time_experience": 1,
    "experience_note": "Five years in one company.",
    "seniority": "mid",
    "education": [
        {"degree": "BSc Electrical Engineering", "institution": None, "finished": "2019"}
    ],
    "languages": [
        {
            "language": "English",
            "level_as_written": "fluent",
            "cefr": "C1",
            "cefr_is_estimate": True,
        }
    ],
    "target_roles": ["Hardware Engineer"],
    "target_fields": ["Electronics"],
    "preferences": ["full-time"],
    "work_mode_preference": "not_stated",
    "dealbreakers": [],
    "work_authorisation": None,
    "ignored_as_application_specific": ["Company name: Example Corp"],
}


class RecordingAdapter(ProviderAdapter):
    def __init__(self):
        super().__init__("fake-key")
        self.calls = []

    def complete_json(self, **request):
        self.calls.append(request)
        return RawReply(json.dumps(PROFILE), Usage(100, 50))

    def list_models(self):
        return []


@pytest.fixture
def settings():
    s = Settings()
    s.ai.provider = "openai"
    s.ai.model = "everyday-model"
    s.ai.reasoning_model = "careful-model"
    return s


def test_profile_uses_the_careful_model_and_the_rules(settings):
    adapter = RecordingAdapter()
    profile = read_profile(AIClient(settings, adapter=adapter), "CV TEXT", "LETTER TEXT")
    assert isinstance(profile, Profile)
    call = adapter.calls[0]
    assert call["model"] == "careful-model"
    system = call["system"]
    assert "Do not rate, grade, critique" in system
    assert "Never guess nationality" in system
    assert "one particular job application" in system
    assert "Where the person wants to work is chosen separately" in system
    assert "full-time work" in system
    assert "<<<CV\nCV TEXT\nCV>>>" in call["prompt"]
    assert "<<<COVER_LETTER\nLETTER TEXT\nCOVER_LETTER>>>" in call["prompt"]


@pytest.fixture
def client():
    return TestClient(create_app(), base_url="http://127.0.0.1:8765")


HEADERS = {"X-Jobcu": "1"}


def test_upload_list_and_remove_documents(client):
    response = client.post(
        "/api/documents/cv",
        files={"file": ("My CV.pdf", make_pdf(FAKE_CV_LINES), "application/pdf")},
        headers=HEADERS,
    )
    assert response.status_code == 200
    listed = client.get("/api/documents").json()
    assert listed["documents"]["cv"]["original_name"] == "My CV.pdf"
    assert listed["documents"]["cover_letter"] is None
    client.delete("/api/documents/cv", headers=HEADERS)
    assert client.get("/api/documents").json()["documents"]["cv"] is None


def test_bad_upload_explains_the_problem(client):
    response = client.post(
        "/api/documents/cv", files={"file": ("cv.png", b"x" * 100, "image/png")}, headers=HEADERS
    )
    assert response.status_code == 400
    assert "PDF or DOCX" in response.json()["detail"]


def test_upload_needs_the_jobcu_header(client):
    files = {"file": ("cv.pdf", b"%PDF", "application/pdf")}
    response = client.post("/api/documents/cv", files=files)
    assert response.status_code == 403


def test_preview_without_documents_explains_what_to_do(client):
    data = client.post("/api/profile/preview", headers=HEADERS).json()
    assert data == {"profile": None, "error": "Please upload your CV first."}


def test_preview_returns_the_profile(client, monkeypatch):
    documents.save_upload("cv", "cv.pdf", make_pdf(FAKE_CV_LINES))
    documents.save_upload("cover_letter", "letter.txt", b"I enjoy hardware design work. " * 5)
    seen = {}

    def fake_read_profile(ai_client, cv_text, letter_text, about_you):
        seen["texts"] = (cv_text, letter_text, about_you)
        return Profile.model_validate(PROFILE), False

    monkeypatch.setattr("jobcu.documents_api.read_profile_reusing", fake_read_profile)
    data = client.post("/api/profile/preview", headers=HEADERS).json()
    assert data["error"] is None
    assert data["profile"]["seniority"] == "mid"
    assert "embedded systems" in seen["texts"][0] and seen["texts"][2] == ""
    # The note is used as typed, before any search saved it.
    client.post("/api/profile/preview", headers=HEADERS, json={"about_you": "Irish citizen"})
    assert seen["texts"][2] == "Irish citizen"


def test_unchanged_documents_are_not_read_again(settings):
    """The owner's rule: only understanding the person may be reused, never the job search."""
    adapter = RecordingAdapter()
    client = AIClient(settings, adapter=adapter)
    first, reused = read_profile_reusing(client, "CV TEXT", "LETTER TEXT")
    assert not reused and len(adapter.calls) == 1
    again, reused = read_profile_reusing(client, "CV TEXT", "LETTER TEXT")
    assert reused and len(adapter.calls) == 1 and again == first
    # A changed document, or a different model, means reading them again.
    read_profile_reusing(client, "CV TEXT (updated)", "LETTER TEXT")
    assert len(adapter.calls) == 2
    settings.ai.reasoning_model = "another-model"
    read_profile_reusing(AIClient(settings, adapter=adapter), "CV TEXT", "LETTER TEXT")
    assert len(adapter.calls) == 3


def test_the_persons_note_is_read_with_the_documents_and_changes_the_profile(settings):
    adapter = RecordingAdapter()
    client = AIClient(settings, adapter=adapter)
    read_profile_reusing(client, "CV TEXT", "LETTER TEXT")
    assert "NOTE" not in adapter.calls[0]["prompt"]
    read_profile_reusing(client, "CV TEXT", "LETTER TEXT", "  Irish citizen  ")
    assert len(adapter.calls) == 2
    assert "<<<NOTE\nIrish citizen\nNOTE>>>" in adapter.calls[1]["prompt"]
    assert "the note explicitly state" in adapter.calls[1]["system"]
    _, reused = read_profile_reusing(client, "CV TEXT", "LETTER TEXT", "Irish citizen")
    assert reused and len(adapter.calls) == 2


def test_the_note_is_kept_with_the_search_form(client, monkeypatch):
    monkeypatch.setattr("jobcu.search.manager.start", lambda form: _Started(form))
    form = {"location_text": "", "about_you": "Irish citizen", "posted_within_hours": 24,
            "job_types": ["full_time_permanent"], "exclude_remote": False}
    assert client.post("/api/search", headers=HEADERS, json=form).status_code == 200
    assert client.get("/api/search/form").json()["about_you"] == "Irish citizen"


class _Started:
    def __init__(self, form):
        self.form = form

    def snapshot(self):
        return {"form": self.form.model_dump()}
