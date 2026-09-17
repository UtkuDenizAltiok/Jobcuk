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
