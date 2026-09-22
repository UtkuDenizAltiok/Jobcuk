import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("guard", ROOT / "tools" / "check_no_secrets.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

# Fake keys are assembled at runtime so this file itself never contains one.
FAKE_KEYS = {
    "anthropic": "sk-" + "ant-api03-" + "A1b2" * 10,
    "openai": "sk-" + "proj-" + "A1b2" * 10,
    "google": "AI" + "za" + "A1b2C3d4" * 4 + "xyz",
    "github": "gh" + "p_" + "A1b2" * 9,
    "private key": "-----BEGIN " + "RSA PRIVATE KEY-----",
    "assignment": 'api_key = "' + "A1b2" * 5 + '"',
}


@pytest.mark.parametrize("kind", FAKE_KEYS)
def test_keys_in_file_content_are_found(kind):
    text = f"first line\nsomething = {FAKE_KEYS[kind]}\n"
    problems = guard.check_text("config.py", text)
    assert problems and "line 2" in problems[0]


def test_allow_marker_skips_a_line():
    text = f"x = '{FAKE_KEYS['openai']}'  # " + "jobcu-guard: allow"
    assert guard.check_text("tests/example.py", text) == []


@pytest.mark.parametrize(
    "text",
    [
        "api_key = settings.get('adzuna_app_key')",
        "The task-based approach sk-short",
        'token = ""',
        "def ask_model(prompt): ...",
    ],
)
def test_normal_code_is_not_flagged(text):
    assert guard.check_text("jobcu/example.py", text) == []


@pytest.mark.parametrize(
    "path",
    [
        "My CV.pdf",
        "docs/cover_letter.DOCX",
        "jobcu.db",
        "data/jobcu.sqlite3",
        "keys.json",
        ".env",
        ".env.local",
        "tests/fake_cv.pdf",
    ],
)
def test_personal_and_secret_file_types_are_blocked(path):
    assert guard.check_path(path)


@pytest.mark.parametrize(
    "path",
    [
        ".env.example",
        "src/jobcu/app.py",
        "docs/images/step-1.png",
    ],
)
def test_normal_files_are_allowed(path):
    assert guard.check_path(path) == []


def test_binary_files_are_not_scanned_as_text():
    content = b"\x89PNG\0" + FAKE_KEYS["openai"].encode()
    assert guard.check_file("docs/images/step.png", content) == []


@pytest.mark.skipif(
    shutil.which("git") is None
    or subprocess.run(["git", "-C", str(ROOT), "rev-parse"], capture_output=True).returncode != 0,
    reason="needs a git checkout",
)
def test_the_repository_itself_is_clean(monkeypatch):
    monkeypatch.chdir(ROOT)
    assert guard.main(["--all"]) == 0
