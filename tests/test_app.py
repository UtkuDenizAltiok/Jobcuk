import re

import pytest
from fastapi.testclient import TestClient

from jobcu import COPYRIGHT, __version__
from jobcu.app import WEB_DIR, create_app

LOCAL_URL = "http://127.0.0.1:8765"


@pytest.fixture
def client():
    return TestClient(create_app(), base_url=LOCAL_URL)


def test_home_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>Jobcu</title>" in response.text
    assert "default-src 'self'" in response.headers["content-security-policy"]


@pytest.mark.parametrize("name", ["style.css", "app.js", "favicon.svg"])
def test_static_files_are_served(client, name):
    assert client.get(f"/static/{name}").status_code == 200


def test_health(client):
    data = client.get("/api/health").json()
    assert data["app"] == "jobcu" and data["version"] == __version__


def test_about_shows_version_copyright_and_data_folder(client, temporary_data_dir):
    about = client.get("/api/about").json()
    assert about["version"] == __version__
    assert about["copyright"] == COPYRIGHT
    assert about["data_folder"] == str(temporary_data_dir.resolve())


def test_requests_for_other_host_names_are_refused():
    client = TestClient(create_app(), base_url="http://evil.example")
    assert client.get("/api/health").status_code == 400


def test_changes_without_jobcu_header_are_refused(client):
    assert client.post("/api/health").status_code == 403


def test_changes_from_another_website_are_refused(client):
    headers = {"X-Jobcu": "1", "Origin": "http://evil.example"}
    assert client.post("/api/health", headers=headers).status_code == 403


def test_changes_from_jobcu_page_pass_the_check(client):
    headers = {"X-Jobcu": "1", "Origin": LOCAL_URL}
    # 405 = allowed through the safety check; this address just doesn't accept changes.
    assert client.post("/api/health", headers=headers).status_code == 405


def test_screen_never_loads_anything_from_the_internet():
    for file in WEB_DIR.iterdir():
        if file.suffix in {".html", ".css", ".js"}:
            text = file.read_text(encoding="utf-8")
            assert not re.search(r"https?://|//[a-z0-9.-]+\.[a-z]{2,}/", text), file.name
