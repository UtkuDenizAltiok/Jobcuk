"""Looking the best jobs up online: where they are and what they ask (jobplace.py)."""

from datetime import UTC, datetime

from jobcu import jobplace
from jobcu.ai.base import AILimitReached, ResearchReply, Source, Usage
from jobcu.dedupe import group_duplicates
from jobcu.sources.base import FoundJob

NOW = datetime.now(UTC)


class Researcher:
    """Stands in for the AI client: answers each web look-up with the next scripted notes, and
    each structuring step with the next scripted jobs."""

    def __init__(self, notes, structured=()):
        self.notes = list(notes)
        self.structured = list(structured)
        self.prompts = []
        self.structure_prompts = []

    def research(self, **request):
        self.prompts.append(request["prompt"])
        answer = self.notes.pop(0)
        if isinstance(answer, Exception):
            raise answer
        searched = 0 if answer.startswith("FROM MEMORY") else 1
        return ResearchReply(answer, [Source("https://jobs.test/a", "Board")],
                             Usage(10, 5, web_searches=searched))

    def generate(self, output, **request):
        self.structure_prompts.append(request["prompt"])
        return output.model_validate({"jobs": self.structured.pop(0)})


def jobs(*places):
    found = [FoundJob(source="adzuna", source_job_id=str(i), url="https://x", title=f"Job {i}",
                      company="Acme", location_text=place, country=country, posted_at=NOW,
                      description="Ein spannendes Team.")
             for i, (place, country) in enumerate(places)]
    return group_duplicates(found, {"adzuna": "aggregator"})


def online(job_id, towns=(), languages=(), years=None, found=True):
    return {"id": job_id, "found": found, "towns": list(towns),
            "languages_asked": [{"language": language, "level": level, "must_have": must}
                                for language, level, must in languages],
            "years_required": years, "doctorate": "not_required",
            "citizenship_or_clearance": "no_such_requirement", "citizenship_or_clearance_words": ""}


def test_only_jobs_nothing_places_are_looked_up():
    groups = jobs(("Deutschland", "DE"), ("München", "DE"), ("", None))
    assert [jobplace.needs_looking_up(g) for g in groups] == [True, False, False]
    groups[0].place_from_web = []
    assert not jobplace.needs_looking_up(groups[0])  # looked up already, never again


def test_towns_found_online_count_only_when_real_and_in_the_job_s_country():
    groups = jobs(*[("Deutschland", "DE")] * 6)
    first = [online("J0", ["Freiburg im Breisgau"]),
             online("J1", ["Wietmarschen-Lohne; Berlin"]),  # two sites
             online("J2", found=False),
             online("J3", ["Bayern"]),  # a region, not a town
             online("J4", ["Vienna"])]  # not in Germany
    researcher = Researcher(["notes", "notes"], [first, []])  # J5: not answered at all
    looked_up = jobplace.find_online(researcher, groups, list(range(6)))
    assert looked_up.towns_found == 2 and looked_up.asked == set(range(6))
    assert [g.place_from_web for g in groups] == [
        ["Freiburg im Breisgau"], ["Wietmarschen-Lohne", "Berlin"], [], [], [], []]
    assert len(researcher.prompts) == 2  # five jobs per request
    assert "J0 | Job 0 | Acme | DE | Ein spannendes Team." in researcher.prompts[0]
    assert researcher.structure_prompts[0].endswith("Research notes:\nnotes")


def test_looking_up_stops_when_the_search_s_allowance_is_used():
    groups = jobs(*[("UK", "GB")] * 7)
    researcher = Researcher(["notes", AILimitReached("used up")],
                            [[online("J0", ["Leeds"])]])
    looked_up = jobplace.find_online(researcher, groups, list(range(7)))
    assert looked_up.towns_found == 1 and looked_up.asked == set(range(5))
    assert groups[0].place_from_web == ["Leeds"]
    assert groups[5].place_from_web is None  # not looked up: can be later


def test_the_full_ad_found_online_gives_its_languages_and_years():
    groups = jobs(("Deutschland", "DE"), ("Radeberg", "DE"), ("Dresden", "DE"))
    answer = [online("J0", ["Radeberg"], [("German", "B2", True), ("English", "B2", False)], 3),
              online("J1"),
              online("J2", found=False)]
    looked_up = jobplace.find_online(Researcher(["notes"], [answer]), groups, [0, 1, 2])
    found = looked_up.requirements
    assert set(found) == {0, 1}
    assert [(a.language, a.level, a.must_have) for a in found[0].languages] == [
        ("German", "B2", True), ("English", "B2", False)]
    assert found[0].years_required == 3
    assert found[1].languages == [] and found[1].years_required is None
    assert found[0].blockers == {"doctorate": "not_required",
                                 "citizenship_or_clearance": "no_such_requirement",
                                 "citizenship_or_clearance_words": ""}
    # Only the job without a town gets one from the answer; the others keep theirs.
    assert groups[0].place_from_web == ["Radeberg"]
    assert all(g.place_from_web is None for g in groups[1:])


def test_an_answer_given_without_searching_the_web_is_asked_again_then_ignored():
    groups = jobs(("Deutschland", "DE"), ("Deutschland", "DE"))
    answer = [online("J0", ["Hamburg"], [("German", "B2", True)]), online("J1")]
    researcher = Researcher(["FROM MEMORY", "notes"], [answer])
    looked_up = jobplace.find_online(researcher, groups, [0, 1])
    assert len(researcher.prompts) == 2 and set(looked_up.requirements) == {0, 1}
    assert groups[0].place_from_web == ["Hamburg"]

    groups = jobs(("Deutschland", "DE"), ("Deutschland", "DE"))
    researcher = Researcher(["FROM MEMORY", "FROM MEMORY"])
    looked_up = jobplace.find_online(researcher, groups, [0, 1])
    assert len(researcher.prompts) == 2 and not researcher.structure_prompts
    assert looked_up.requirements == {} and looked_up.asked == {0, 1}
    assert [g.place_from_web for g in groups] == [[], []]  # asked, nothing to trust


def test_summaries_that_could_make_the_list_are_looked_up_for_their_requirements():
    group = jobs(("Dresden", "DE"))[0]
    scored = {"score": 50, "evidence": {}}
    assert jobplace.needs_requirements(group, scored)
    assert not jobplace.needs_requirements(group, {**scored, "score": 49})
    assert not jobplace.needs_requirements(group, {**scored, "read_online": True})
    assert not jobplace.needs_requirements(group, {"score": 80})  # scored by an older Jobcu
    group.copies[0].description_is_complete = True
    assert not jobplace.needs_requirements(group, scored)
