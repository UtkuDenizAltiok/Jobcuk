"""Career-site titles the search words miss get a quick look from the person's AI instead of
being dropped unseen (search with the owner's CV, 2026-09-24: 2,377 fresh titles failed the
words, among them "R&D Electrical Engineering Graduate Program" for a hardware engineer)."""

import json
import re
from datetime import UTC, datetime

from test_search import PROFILE, FakeAI, FakeSource, ready, wait_until_done  # noqa: F401

from jobcu import relevance, search
from jobcu.ai.base import RawReply, Usage
from jobcu.profile import Profile
from jobcu.settings import SearchForm
from jobcu.sources.base import FoundJob


class ScreeningAI(FakeAI):
    """Keeps the titles that mention electrical or RF work."""

    def __init__(self):
        super().__init__()
        self.batches = 0

    def complete_json(self, **request):
        if request["schema_name"] == "TitleScreen":
            self.batches += 1
            ids = re.findall(r"^(T\d+) \| [^|]*(?:Electrical|RF)", request["prompt"], re.MULTILINE)
            return RawReply(json.dumps({"worth_a_look": ids + ["T99999"]}), Usage(10, 5))
        return super().complete_json(**request)


class CareerSite(FakeSource):
    """A career site: its titles come without ads, and some miss the search words."""

    id = "careersite"
    name = "Company career sites (Fake)"
    kind = "employer"

    def search(self, query, ctx):
        yield from super().search(query, ctx)
        for i, title in enumerate(["R&D Electrical Engineering Graduate Program",
                                   "Account Executive", "RF Design Engineer"]):
            ctx.report.requests += 1
            yield FoundJob(source=self.id, source_job_id=f"c{i}", url=f"https://careers.test/{i}",
                           title=title, company="Acme", location_text="Berlin", country="DE",
                           posted_at=datetime.now(UTC), date_precision="exact",
                           title_unmatched=True)


def test_titles_are_looked_at_in_batches_and_only_real_ids_count(monkeypatch):
    monkeypatch.setattr(relevance, "TITLE_BATCH", 2)
    ai = ScreeningAI()

    class Client:
        def generate(self, output, **request):
            reply = ai.complete_json(schema_name=output.__name__, **request)
            return output.model_validate_json(reply.text)

    titles = [("Electrical Design Engineer", "A"), ("Accountant", "B"), ("RF Engineer", "C"),
              ("Chef", None)]
    kept = relevance.screen_titles(Client(), Profile.model_validate(PROFILE), titles)
    assert kept == {0, 2} and ai.batches == 2


def test_a_search_keeps_the_titles_the_ai_picks_and_says_how_many(ready, monkeypatch):  # noqa: F811
    ai = ScreeningAI()
    monkeypatch.setattr("jobcu.ai.client.AIClient.adapter", lambda self: ai)
    monkeypatch.setattr("jobcu.pipeline.all_sources", lambda: [CareerSite()])
    manager = search.SearchManager()
    manager.start(SearchForm(location_text="Germany"))
    result = wait_until_done(manager)
    assert result["status"] == "finished", result["error"]
    step = next(s for s in result["steps"] if s["id"] == "sources")
    assert step["detail"] == ("5 job ads found (2 of 3 more titles from company career sites "
                              "kept by your AI)")
    titles = {card["title"] for card in result["result"]["jobs"]["cards"]}
    assert {"R&D Electrical Engineering Graduate Program", "RF Design Engineer"} <= titles
    assert "Account Executive" not in titles
    report = next(s for s in result["result"]["jobs"]["sources"]
                  if s["name"] == CareerSite.name)
    assert report["jobs_found"] == 5
