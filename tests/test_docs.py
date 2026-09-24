import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = sorted(
    [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md"), *(ROOT / ".github").rglob("*.md")]
)
LINK = re.compile(r"\]\(([^)\s]+)\)")


@pytest.mark.parametrize("doc", MARKDOWN_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_links_between_documents_work(doc):
    for target in LINK.findall(doc.read_text(encoding="utf-8")):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue  # web links and links within the same page
        path = (doc.parent / target.split("#")[0]).resolve()
        assert path.exists(), f"{doc.relative_to(ROOT)} links to missing {target}"


def test_ai_tools_all_read_the_shared_instructions():
    assert (ROOT / "CLAUDE.md").read_text(encoding="utf-8").strip() == "@AGENTS.md"
    gemini = json.loads((ROOT / ".gemini" / "settings.json").read_text(encoding="utf-8"))
    assert gemini["context"]["fileName"] == "AGENTS.md"
    assert "read: AGENTS.md" in (ROOT / ".aider.conf.yml").read_text(encoding="utf-8")


# The records stay usable after any interruption only if their structure holds (AGENTS.md,
# "Where everything lives" and "Sessions").

def _project_map() -> str:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    return text.split("## Project layout", 1)[1].split("## Commands", 1)[0]


def test_the_project_map_lists_every_module_and_tool():
    listed = _project_map()
    package = ROOT / "src" / "jobcu"
    names = [p.name for p in package.glob("*.py") if p.name != "__init__.py"]
    names += [f"{p.name}/" for p in package.iterdir() if p.is_dir() and not p.name.startswith("_")]
    names += [f"tools/{p.name}" for p in (ROOT / "tools").glob("*.py")]
    missing = [name for name in names if name not in listed]
    assert not missing, f"AGENTS.md's project map doesn't mention {missing}"


def test_progress_keeps_the_sections_a_new_session_needs():
    text = (ROOT / "docs" / "PROGRESS.md").read_text(encoding="utf-8")
    right_now = text.split("## Right now", 1)[1].split("\n## ", 1)[0]
    assert re.search(r"\*Updated \d{4}-\d{2}-\d{2}\.", right_now)
    for section in ("State", "In progress", "Verify before relying on", "Waiting on the owner",
                    "Next tasks", "Known limitations"):
        assert f"### {section}" in right_now, f"'Right now' lost its '{section}' section"


def test_the_prompts_for_ai_assistants_point_at_real_sections():
    prompts = " ".join((ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").split())
    rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for section in ("Starting, or resuming after any interruption", "Ending a session"):
        assert section in prompts and f"### {section}" in rules


def test_cloud_sessions_are_prepared_by_the_repository():
    # AGENTS.md, "Working in a cloud session": the hook runs the setup script, which does nothing
    # on people's own computers.
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    (hook,) = settings["hooks"]["SessionStart"]
    assert "tools/cloud_setup.sh" in hook["hooks"][0]["command"]
    script = (ROOT / "tools" / "cloud_setup.sh").read_text(encoding="utf-8")
    assert 'if [ "$CLAUDE_CODE_REMOTE" != "true" ]' in script and "uv sync" in script
    assert "tools/cloud_setup.sh" in _project_map()
