"""Finding where a job is online, when nothing Jobcu has says (jobplace.py)."""

from datetime import UTC, datetime

from jobcu import jobplace
from jobcu.ai.base import AILimitReached, ResearchReply, Source, Usage
from jobcu.dedupe import group_duplicates
from jobcu.sources.base import FoundJob

NOW = datetime.now(UTC)


class Researcher:
    """Stands in for the AI client: answers each web look-up with the next scripted text."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def research(self, **request):
        self.prompts.append(request["prompt"])
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return ResearchReply(answer, [Source("https://jobs.test/a", "Board")], Usage(10, 5))


def jobs(*places):
    found = [FoundJob(source="adzuna", source_job_id=str(i), url="https://x", title=f"Job {i}",
                      company="Acme", location_text=place, country=country, posted_at=NOW,
                      description="Ein spannendes Team.")
             for i, (place, country) in enumerate(places)]
    return group_duplicates(found, {"adzuna": "aggregator"})


def test_only_jobs_nothing_places_are_looked_up():
    groups = jobs(("Deutschland", "DE"), ("München", "DE"), ("", None))
    assert [jobplace.needs_looking_up(g) for g in groups] == [True, False, False]
    groups[0].place_from_web = []
    assert not jobplace.needs_looking_up(groups[0])  # looked up already, never again


def test_towns_found_online_count_only_when_real_and_in_the_job_s_country():
    groups = jobs(*[("Deutschland", "DE")] * 6)
    answer = "\n".join([
        "J0 | Freiburg im Breisgau",
        "**J1** | Wietmarschen-Lohne; Berlin",  # markdown and two sites
        "J2 | unknown",
        "J3 | Bayern",  # a region, not a town
        "J4 | Vienna",  # not in Germany
        # J5 not answered at all
    ])
    researcher = Researcher(answer, "")
    looked_up = jobplace.find_online(researcher, groups, list(range(6)))
    assert looked_up.towns_found == 2 and looked_up.asked == set(range(6))
    assert looked_up.requirements == {}  # town-only answers say nothing about requirements
    assert [g.place_from_web for g in groups] == [
        ["Freiburg im Breisgau"], ["Wietmarschen-Lohne", "Berlin"], [], [], [], []]
    assert len(researcher.prompts) == 2  # five jobs per request
    assert "J0 | Job 0 | Acme | DE | Ein spannendes Team." in researcher.prompts[0]


def test_looking_up_stops_when_the_search_s_allowance_is_used():
    groups = jobs(*[("UK", "GB")] * 7)
    researcher = Researcher("J0 | Leeds", AILimitReached("used up"))
    looked_up = jobplace.find_online(researcher, groups, list(range(7)))
    assert looked_up.towns_found == 1 and looked_up.asked == set(range(5))
    assert groups[0].place_from_web == ["Leeds"]
    assert groups[5].place_from_web is None  # not looked up: can be later


def test_the_full_ad_found_online_gives_its_languages_and_years():
    groups = jobs(("Deutschland", "DE"), ("Radeberg", "DE"), ("Dresden", "DE"),
                  ("Leipzig", "DE"), ("Berlin", "DE"))
    answer = "\n".join([
        "J0 | Radeberg | German B2 must; English B2+ plus | 3",
        "J1 | no town | none | none",
        "J2 | not found",
        "J3 | Leipzig | German fluent must | 2",  # not a level: not trusted
        "J4 | Berlin | German not needed must; English C1 must | 5+ years",
    ])
    looked_up = jobplace.find_online(Researcher(answer), groups, list(range(5)))
    found = looked_up.requirements
    assert set(found) == {0, 1, 4}
    assert [(a.language, a.level, a.must_have) for a in found[0].languages] == [
        ("German", "B2", True), ("English", "B2", False)]
    assert found[0].years_required == 3
    assert found[1].languages == [] and found[1].years_required is None
    assert [(a.language, a.level) for a in found[4].languages] == [
        ("German", "not_needed"), ("English", "C1")]
    assert found[4].years_required == 5
    # Only the job without a town gets one from the answer; the others keep theirs.
    assert groups[0].place_from_web == ["Radeberg"]
    assert all(g.place_from_web is None for g in groups[1:])


def test_only_summaries_near_the_top_are_looked_up_for_their_requirements():
    group = jobs(("Dresden", "DE"))[0]
    scored = {"score": 80, "evidence": {}}
    assert jobplace.needs_requirements(group, scored)
    assert not jobplace.needs_requirements(group, {**scored, "score": 69})
    assert not jobplace.needs_requirements(group, {**scored, "read_online": True})
    assert not jobplace.needs_requirements(group, {"score": 80})  # scored by an older Jobcu
    group.copies[0].description_is_complete = True
    assert not jobplace.needs_requirements(group, scored)
