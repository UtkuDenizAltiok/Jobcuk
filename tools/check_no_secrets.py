"""Safety check: blocks API keys, CVs and other personal data from the repository.

It runs automatically:
- on this computer before every commit (.githooks/pre-commit)
- on GitHub after every upload (.github/workflows/tests.yml)

Usage:
    python tools/check_no_secrets.py --staged   check the files about to be committed
    python tools/check_no_secrets.py --all      check every file in the repository

A line containing "jobcu-guard: allow" is skipped. Use it only for values that
are obviously fake.

Uses only Python's standard library, so it works without installing anything.
"""

import argparse
import re
import subprocess
import sys
from pathlib import PurePosixPath

ALLOW_MARKER = "jobcu-guard: allow"

# Fake CVs and cover letters for tests may live here, named fake_*.
FAKE_DOCUMENTS_DIR = "tests/fixtures/fake_documents/"

DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".odt", ".rtf", ".pages"}
ALWAYS_BLOCKED_EXTENSIONS = {
    ".db", ".db-journal", ".db-wal", ".db-shm", ".sqlite", ".sqlite3",
    ".key", ".pem", ".p12", ".pfx",
}
BLOCKED_FILENAMES = {"keys.json", "keys.json.damaged", "secrets.json", ".env"}

SECRET_PATTERNS = [
    ("an Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("an OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("a Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    (
        "a GitHub token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})"),
    ),
    ("an AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("a Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("a Groq API key", re.compile(r"\bgsk_[A-Za-z0-9]{40,}")),
    ("an xAI API key", re.compile(r"\bxai-[A-Za-z0-9]{40,}")),
    ("a Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("a private key", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
    (
        "a key or password written into a file",
        re.compile(
            r"(?i)\b(?:api[_-]?key|app[_-]?key|secret|token|password|passwd)\b[\"']?\s*[:=]\s*"
            r"[\"'][A-Za-z0-9_\-+/=.]{16,}[\"']"
        ),
    ),
]


def check_path(path: str) -> list[str]:
    """Problems caused by the file's name or type alone."""
    posix = PurePosixPath(path.replace("\\", "/"))
    name = posix.name.lower()
    suffix = posix.suffix.lower()
    if name in BLOCKED_FILENAMES or (name.startswith(".env.") and name != ".env.example"):
        return [f"{path}: files like this hold keys or passwords"]
    if suffix in ALWAYS_BLOCKED_EXTENSIONS:
        return [f"{path}: database and key files can hold personal data or secrets"]
    if suffix in DOCUMENT_EXTENSIONS:
        in_fake_dir = str(posix).startswith(FAKE_DOCUMENTS_DIR)
        if not (in_fake_dir and name.startswith("fake_")):
            return [
                f"{path}: documents such as CVs and cover letters must not be committed "
                f"(fake test documents go in {FAKE_DOCUMENTS_DIR}, named fake_*)"
            ]
    return []


def check_text(path: str, text: str) -> list[str]:
    """Problems found inside the file's content."""
    problems = []
    for number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                problems.append(f"{path}, line {number}: looks like {label}")
                break
    return problems


def check_file(path: str, content: bytes) -> list[str]:
    problems = check_path(path)
    if problems or b"\0" in content[:8192]:  # skip binary files such as images
        return problems
    return check_text(path, content.decode("utf-8", errors="replace"))


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def _files(staged: bool) -> list[str]:
    if staged:
        output = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    else:
        output = _git("ls-files", "-z")
    return [name for name in output.decode("utf-8").split("\0") if name]


def _content(path: str, staged: bool) -> bytes:
    if staged:
        return _git("show", f":{path}")
    with open(path, "rb") as file:
        return file.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="check files about to be committed")
    group.add_argument("--all", action="store_true", help="check every file in the repository")
    args = parser.parse_args(argv)

    problems = []
    for path in _files(staged=args.staged):
        try:
            content = _content(path, staged=args.staged)
        except (OSError, subprocess.CalledProcessError):
            continue  # e.g. a file deleted but not yet committed
        problems.extend(check_file(path, content))

    if problems:
        print("Jobcu safety check: STOPPED. These files may contain keys or personal data:")
        for problem in problems:
            print(f"  - {problem}")
        print("Nothing was committed or uploaded. Remove these from the commit and try again.")
        return 1
    print("Jobcu safety check: OK, no keys or personal data found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
