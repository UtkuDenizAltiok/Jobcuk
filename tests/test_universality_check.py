"""The made-up people in tools/universality_check.py stay consistent (no AI is called here)."""

import importlib.util
from pathlib import Path

from jobcu.countries import LANGUAGE_NAMES

TOOL = Path(__file__).resolve().parent.parent / "tools" / "universality_check.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("universality_check", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_made_up_person_can_be_checked():
    tool = load_tool()
    titles = [title for title, _ in tool.MIXED_TITLES]
    assert len({person.key for person in tool.PEOPLE}) == len(tool.PEOPLE) >= 5
    for person in tool.PEOPLE:
        # The quick check is judged on the person's own titles, so they must be in the list.
        assert person.related_titles and set(person.related_titles) <= set(titles)
        assert sorted(ad.expect for ad in person.ads) == ["high", "low", "middle"]
        assert "en" in person.languages
        assert all(code in LANGUAGE_NAMES for code in person.languages)
        assert person.cv.strip() and person.esco_query[1] in LANGUAGE_NAMES
