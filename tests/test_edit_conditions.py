"""Correcting the location conditions after a search (HANDOVER section 6, "Edit").

The person can switch a condition off, correct its towns or its size, reword it (Jobcu checks it
again) or add one. The corrections are applied to the jobs the search already found: jobs that
come back in are checked and scored, and nothing already worked out is asked of the AI twice.
"""

import json
import re
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from test_location_conditions import ScriptedClient
from test_search import HEADERS, PROFILE, WORDS, FakeAI, ready, wait_until_done  # noqa: F401

from jobcu import pool, search
from jobcu.ai.base import RawReply, ResearchReply, Source, Usage
from jobcu.app import create_app
from jobcu.dedupe import JobGroup
from jobcu.location import (
    CheckedCondition,
    Condition,
    ConditionEdit,
    EditProblem,
    LocationPlan,
    TownRef,
    apply_edits,
    check_edits,
)
from jobcu.settings import SearchForm
from jobcu.sources.base import FoundJob, JobSource

NOW = datetime.now(UTC)
BIG_CITIES = {"text": "only big cities", "understood_as": "Towns with at least 500,000 people",
              "kind": "town_size", "min_people": 500_000, "min_share_of_country": None}


def plan_with(*conditions, countries=("DE",)):
    return LocationPlan(text="…", understood_as="Germany, big cities only.",
                        countries=list(countries), places=[], conditions=list(conditions),
                        not_checked_yet=[], outside_supported_area=[], broad=False)


def avoid(*towns, status="applied"):
    return Condition(text="no far-right strongholds", understood_as="Avoid these towns",
                     status=status, kind="towns_to_avoid",
                     towns=[TownRef(name=name, country="DE") for name in towns])


def size(people=None, share=None):
    return Condition(text="big cities", understood_as="Big towns", status="applied",
                     kind="town_size", min_people=people, min_share_of_country=share)


# --- Reading the corrections ---------------------------------------------------------------


def test_switching_a_condition_off_keeps_it_but_stops_it_filtering():
    plan = apply_edits(ScriptedClient(None), plan_with(avoid("Dresden")),
                       [ConditionEdit(text="no far-right strongholds", original=0, use=False)])
    condition = plan.conditions[0]
    assert condition.switched_off and not condition.filters and plan.edited
    assert condition.towns[0].name == "Dresden"  # switching it back on restores it as it was


def test_corrected_towns_become_the_persons_own_rule():
    plan = plan_with(avoid("Dresden", "Leipzig", status="estimate"))
    edit = ConditionEdit(text="no far-right strongholds", original=0,
                         towns=["Dresden", "München", "Garching bei München"])
    condition = apply_edits(ScriptedClient(None), plan, [edit]).conditions[0]
    assert sorted(town.name for town in condition.towns) == ["Dresden", "Garching", "Munich"]
    assert condition.changed_by_you and condition.status == "applied"


def test_unchanged_towns_are_not_counted_as_a_change():
    plan = plan_with(avoid("Dresden", "Leipzig", status="estimate"))
    edit = ConditionEdit(text="no far-right strongholds", original=0, towns=["Leipzig", "Dresden"])
    condition = apply_edits(ScriptedClient(None), plan, [edit]).conditions[0]
    assert not condition.changed_by_you and condition.status == "estimate"


def test_unknown_towns_and_empty_lists_are_explained_before_any_ai_is_used():
    plan = plan_with(avoid("Dresden"), countries=("DE", "IE"))
    with pytest.raises(EditProblem, match="doesn't know Atlantis"):
        check_edits(plan, [ConditionEdit(text="no far-right strongholds", original=0,
                                         towns=["Dresden", "Atlantis"])])
    with pytest.raises(EditProblem, match="at least one place"):
        check_edits(plan, [ConditionEdit(text="no far-right strongholds", original=0, towns=[])])
    with pytest.raises(EditProblem, match="open it again"):
        check_edits(plan, [ConditionEdit(text="gone", original=3)])


def test_with_one_country_searched_a_name_jobcu_doesnt_know_is_still_accepted():
    # Small places are missing from the town list; a job whose place is written that way still
    # matches the name.
    edit = ConditionEdit(text="no far-right strongholds", original=0, towns=["Kleinstadtdorf"])
    condition = apply_edits(ScriptedClient(None), plan_with(avoid("Dresden")), [edit]).conditions[0]
    assert [(town.name, town.country) for town in condition.towns] == [("Kleinstadtdorf", "DE")]


def test_a_corrected_size_is_used_in_the_unit_it_was_written_in():
    plan = apply_edits(ScriptedClient(None), plan_with(size(people=500_000), size(share=0.003)), [
        ConditionEdit(text="big cities", original=0, min_people=100_000),
        ConditionEdit(text="big cities", original=1, min_share_of_country=0.001),
    ])
    assert plan.conditions[0].min_people == 100_000 and plan.conditions[0].changed_by_you
    assert plan.conditions[1].min_share_of_country == 0.001
    with pytest.raises(EditProblem, match="Give a size"):
        check_edits(plan_with(size(people=500_000)),
                    [ConditionEdit(text="big cities", original=0, min_people=0)])


def test_reworded_and_new_conditions_are_checked_again_and_nothing_else_is():
    answer = CheckedCondition(understood_as="Towns on the coast", kind="towns_that_fit",
                              towns=[TownRef(name="Kiel", country="DE")], confidence="checked",
                              note="From the coastline list.")
    client = ScriptedClient(answer)
    plan = apply_edits(client, plan_with(avoid("Dresden"), size(people=500_000)), [
        ConditionEdit(text="towns by the sea", original=0),  # reworded
        ConditionEdit(text="big cities", original=1),  # unchanged
        ConditionEdit(text="  ", original=None),  # an empty new line is ignored
    ])
    assert len(client.research_calls) == 1
    assert [c.understood_as for c in plan.conditions] == ["Towns on the coast", "Big towns"]
    assert plan.conditions[0].towns[0].name == "Kiel"

    again = apply_edits(client, plan_with(avoid("Dresden")), [
        ConditionEdit(text="no far-right strongholds", original=0, check_again=True),
        ConditionEdit(text="a university town", original=None),
    ])
    assert len(client.research_calls) == 3 and len(again.conditions) == 2


def test_conditions_the_window_left_out_stay_as_they_were():
    plan = apply_edits(ScriptedClient(None), plan_with(avoid("Dresden"), size(people=500_000)),
                       [ConditionEdit(text="big cities", original=1, use=False)])
    assert [c.kind for c in plan.conditions] == ["town_size", "towns_to_avoid"]
    assert plan.conditions[0].switched_off and not plan.conditions[1].switched_off


def test_scoring_isnt_told_about_switched_off_conditions():
    from jobcu.profile import Profile
    from jobcu.scoring import _background

    unchecked = Condition(text="Turkish supermarkets nearby", understood_as="Turkish shops",
                          status="not_checked", kind="could_not_check")
    plan = apply_edits(ScriptedClient(None), plan_with(unchecked),
                       [ConditionEdit(text="Turkish supermarkets nearby", original=0, use=False)])
    background = _background(Profile.model_validate(PROFILE), plan)
    assert "Turkish" not in background and "big cities only" not in background


# --- The jobs the search found ---------------------------------------------------------------


def test_the_kept_jobs_survive_a_restart():
    copy = FoundJob(source="s", source_job_id="1", url="https://jobs.test/1", title="Engineer",
                    location_text="Garching", country="DE", posted_at=NOW,
                    date_precision="exact", job_types=["full_time_permanent"])
    kept = pool.Pool(search_id=7, jobs=[pool.PoolJob(JobGroup(copies=[copy]), unrelated=False,
                                                     scored={"score": 80})],
                     profile=PROFILE, left_out={"too_old": 2}, ads_found=3, different_jobs=3)
    pool.save(kept)
    pool.save(pool.Pool(search_id=6, jobs=[], profile=PROFILE))  # an older one isn't kept...
    assert not pool.exists(7)
    pool.save(kept)
    assert not pool.exists(6)  # ...only the latest search's jobs are
    loaded = pool.load(7)
    assert loaded.jobs[0].group.copies[0] == copy
    assert loaded.jobs[0].scored == {"score": 80} and loaded.left_out == {"too_old": 2}


class PlacedSource(JobSource):
    id = "placed"
    name = "Placed Jobs"
    kind = "job_board"
    jobs = [("Hardware Engineer", "Berlin"), ("Electronics Engineer", "Garching bei München"),
            ("Nurse", "Berlin")]

    def search(self, query, ctx):
        for i, (title, place) in enumerate(self.jobs):
            yield FoundJob(source="placed", source_job_id=str(i), url=f"https://jobs.test/{i}",
                           title=title, company=f"Company {i}", location_text=place,
                           country="DE", posted_at=NOW, date_precision="exact",
                           description="Full ad text", description_is_complete=True)


class ConditionAI(FakeAI):
    """The search's AI, with a condition about places in the location text."""

    def __init__(self):
        super().__init__()
        self.scored_titles: list[list[str]] = []
        self.quick_checked: list[list[str]] = []

    def complete_json(self, **request):
        name, prompt = request["schema_name"], request["prompt"]
        if name == "LocationUnderstanding":
            answer = {"understood_as": "Big German cities.", "limits_countries": True,
                      "countries": ["DE"], "places": [],
                      "conditions_about_places": ["only big cities"],
                      "conditions_about_the_job": [], "outside_supported_area": []}
            return RawReply(json.dumps(answer), Usage(10, 5))
        if name == "SortedConditions":
            return RawReply(json.dumps({"conditions": [BIG_CITIES]}), Usage(10, 5))
        if name == "ScoringAnswer":
            self.scored_titles.append(re.findall(r"^Title: (.+)$", prompt, re.MULTILINE))
        if name == "QuickPassAnswer":
            self.quick_checked.append(re.findall(r"^J\d+ \| ([^|]+) \|", prompt, re.MULTILINE))
        return super().complete_json(**request)


@pytest.fixture
def conditions_ready(ready, monkeypatch):  # noqa: F811
    ai = ConditionAI()
    monkeypatch.setattr("jobcu.ai.client.AIClient.adapter", lambda self: ai)
    monkeypatch.setattr("jobcu.pipeline.all_sources", lambda: [PlacedSource()])
    manager = search.SearchManager()
    monkeypatch.setattr(search, "manager", manager)
    return ai, manager


def titles(cards):
    return sorted(card["title"] for card in cards)


def test_corrected_conditions_are_applied_to_the_jobs_already_found(conditions_ready):
    ai, manager = conditions_ready
    run = manager.start(SearchForm(location_text="Germany, only big cities"))
    first = wait_until_done(manager)
    assert first["status"] == "finished", first["error"]
    jobs = first["result"]["jobs"]
    assert titles(jobs["cards"]) == ["Hardware Engineer"]
    assert titles(jobs["ruled_out_by_conditions"]) == ["Electronics Engineer"]
    # A job a condition left out shows what left it out, and nothing else.
    (left_out,) = jobs["ruled_out_by_conditions"][0]["location_checks"]
    assert left_out["status"] == "fails" and left_out["label"].startswith("Towns with at least")
    assert ai.scored_titles == [["Hardware Engineer"]]
    assert sorted(ai.quick_checked[0]) == ["Hardware Engineer", "Nurse"]

    # Switched off: the Garching job comes back, is checked and scored. The Berlin job keeps the
    # score it already had, and the nurse job stays out without being asked about again.
    manager.reapply(run.id, [ConditionEdit(text="only big cities", original=0, use=False)])
    second = wait_until_done(manager)
    assert second["status"] == "finished" and second["kind"] == "reapply", second["error"]
    assert [step["status"] for step in second["steps"]] == ["done"] * 5
    jobs = second["result"]["jobs"]
    assert titles(jobs["cards"]) == ["Electronics Engineer", "Hardware Engineer"]
    assert jobs["ruled_out_by_conditions"] == []
    assert ai.scored_titles == [["Hardware Engineer"], ["Electronics Engineer"]]
    assert ai.quick_checked[1:] == [["Electronics Engineer"]]
    assert jobs["counts"]["unrelated_titles"] == ["Nurse"]
    assert second["result"]["location"]["edited"]
    assert second["result"]["profile"] and second["result"]["search_words"]

    # A smaller size than the first reading: nothing new to score, nothing looked up.
    manager.reapply(run.id, [ConditionEdit(text="only big cities", original=0, min_people=10_000)])
    third = wait_until_done(manager)["result"]
    assert titles(third["jobs"]["cards"]) == ["Electronics Engineer", "Hardware Engineer"]
    assert len(ai.scored_titles) == 2
    garching = next(c for c in third["jobs"]["cards"] if c["title"] == "Electronics Engineer")
    assert garching["location_checks"][-1]["source"] == "Changed by you"


def test_the_edit_api_explains_what_it_cant_do(conditions_ready, monkeypatch):
    _, manager = conditions_ready
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    body = {"location_text": "Germany, only big cities", "posted_within_hours": 24,
            "job_types": ["full_time_permanent"], "exclude_remote": False}
    search_id = client.post("/api/search", json=body, headers=HEADERS).json()["id"]
    wait_until_done(manager)
    current = client.get("/api/search/current").json()["search"]
    assert current["can_edit_conditions"]

    url = f"/api/search/{search_id}/conditions"
    wrong_size = {"conditions": [{"text": "only big cities", "original": 0, "min_people": 0}]}
    response = client.post(url, json=wrong_size, headers=HEADERS)
    assert response.status_code == 400 and "Give a size" in response.json()["detail"]
    assert client.post(f"/api/search/{search_id + 1}/conditions", json={"conditions": []},
                       headers=HEADERS).status_code == 404

    switched_off = {"conditions": [{"text": "only big cities", "original": 0, "use": False}]}
    started = client.post(url, json=switched_off, headers=HEADERS).json()
    assert started["status"] == "running" and started["kind"] == "reapply"
    wait_until_done(manager)

    # After a restart the saved results can still be corrected.
    monkeypatch.setattr(search, "manager", search.SearchManager())
    restored = client.get("/api/search/current").json()["search"]
    assert restored["can_edit_conditions"] and restored["kind"] == "reapply"
    assert len(restored["result"]["jobs"]["cards"]) == 2


# --- Jobs whose job site gives only a country --------------------------------------------------


class CountryOnlySource(JobSource):
    """Like Adzuna's newer ads: "Deutschland" as the place, the town only in the text."""

    id = "countryonly"
    name = "Country Only"
    kind = "aggregator"
    jobs = [("Hardware Engineer", "Wir suchen Sie am Standort in Berlin."),
            ("Electronics Engineer", "Wir suchen Sie am Standort in Garching."),
            ("PCB Designer", "Ein spannendes Team wartet.")]

    def search(self, query, ctx):
        for i, (title, text) in enumerate(self.jobs):
            yield FoundJob(source="countryonly", source_job_id=str(i), url=f"https://jobs.test/{i}",
                           title=title, company=f"Company {i}", location_text="Deutschland",
                           country="DE", posted_at=NOW, date_precision="exact",
                           description=text, description_is_complete=True)


class PlaceReadingAI(ConditionAI):
    """Reads "am Standort in X" for the jobs marked WHERE?, as a real model would."""

    def complete_json(self, **request):
        if request["schema_name"] == "QuickPassAnswer":
            self.quick_checked.append(
                re.findall(r"^J\d+ \| ([^|]+) \|", request["prompt"], re.MULTILINE))
            places = [{"id": job_id, "places": [town]} for job_id, town in re.findall(
                r"^(J\d+) \|.*Standort in (\w+)\..*\| WHERE\?$", request["prompt"], re.MULTILINE)]
            return RawReply(json.dumps({"clearly_unrelated": [], "places": places}), Usage(10, 5))
        return super().complete_json(**request)


def test_the_town_an_ad_names_decides_when_its_site_gave_only_a_country(conditions_ready,
                                                                       monkeypatch):
    _, manager = conditions_ready
    ai = PlaceReadingAI()
    monkeypatch.setattr("jobcu.ai.client.AIClient.adapter", lambda self: ai)
    monkeypatch.setattr("jobcu.pipeline.all_sources", lambda: [CountryOnlySource()])
    run = manager.start(SearchForm(location_text="Germany, only big cities"))
    first = wait_until_done(manager)
    assert first["status"] == "finished", first["error"]
    jobs = first["result"]["jobs"]
    # Berlin fits, Garching is too small, and the ad that names no town is kept, saying why.
    assert titles(jobs["cards"]) == ["Hardware Engineer", "PCB Designer"]
    assert titles(jobs["ruled_out_by_conditions"]) == ["Electronics Engineer"]
    berlin = next(c for c in jobs["cards"] if c["title"] == "Hardware Engineer")
    assert berlin["location"] == "Berlin" and berlin["location_from_ad_text"]
    assert [c["status"] for c in berlin["location_checks"]] == ["verified", "verified"]
    unknown = next(c for c in jobs["cards"] if c["title"] == "PCB Designer")
    assert unknown["location"] == "Deutschland" and not unknown["location_from_ad_text"]
    assert unknown["location_checks"][-1] == {
        "label": "Country Only doesn't say which town this job is in, nor does its text, so "
                 "your condition about places couldn't be checked", "status": "unclear",
        "source": None, "detail": None,
        "whole_sentence": True}
    assert len(ai.quick_checked) == 1

    # Switched off: the Garching job comes back with the town already read, not asked again.
    manager.reapply(run.id, [ConditionEdit(text="only big cities", original=0, use=False)])
    second = wait_until_done(manager)["result"]["jobs"]
    assert titles(second["cards"]) == ["Electronics Engineer", "Hardware Engineer", "PCB Designer"]
    assert len(ai.quick_checked) == 1
    garching = next(c for c in second["cards"] if c["title"] == "Electronics Engineer")
    assert garching["location"] == "Garching" and garching["location_from_ad_text"]
    assert pool.load(run.id).jobs[1].group.place_from_text == ["Garching"]


class OnlineAI(PlaceReadingAI):
    """Also finds ads on the web: the PCB Designer ad is in Garching, a small town."""

    can_search_the_web = True

    def __init__(self):
        super().__init__()
        self.looked_up: list[list[str]] = []

    def research(self, **request):
        jobs = re.findall(r"^(J\d+) \| ([^|]+) \|", request["prompt"], re.MULTILINE)
        self.looked_up.append([title.strip() for _, title in jobs])
        return ResearchReply("The PCB Designer ad is in Garching.",
                             [Source("https://jobs.test/pcb", "Job board")],
                             Usage(100, 20, web_searches=len(jobs)))

    def complete_json(self, **request):
        if request["schema_name"] != "OnlineAnswer":
            return super().complete_json(**request)
        jobs = re.findall(r"^(J\d+) \| ([^|]+) \|", request["prompt"], re.MULTILINE)
        answer = [{"id": job_id, "found": title.startswith("PCB"),
                   "towns": ["Garching"] if title.startswith("PCB") else [],
                   "languages_asked": [], "years_required": None} for job_id, title in jobs]
        return RawReply(json.dumps({"jobs": answer}), Usage(10, 5))


def test_the_town_of_a_good_job_is_found_online_and_the_conditions_decide(conditions_ready,
                                                                         monkeypatch):
    _, manager = conditions_ready
    ai = OnlineAI()
    monkeypatch.setattr("jobcu.ai.client.AIClient.adapter", lambda self: ai)
    monkeypatch.setattr("jobcu.pipeline.all_sources", lambda: [CountryOnlySource()])
    run = manager.start(SearchForm(location_text="Germany, only big cities"))
    result = wait_until_done(manager)
    assert result["status"] == "finished", result["error"]
    jobs = result["result"]["jobs"]
    # Only the job no text placed is looked up; Garching is too small for "only big cities".
    assert ai.looked_up == [["PCB Designer"]]
    assert titles(jobs["cards"]) == ["Hardware Engineer"]
    assert titles(jobs["ruled_out_by_conditions"]) == ["Electronics Engineer", "PCB Designer"]
    assert result["steps"][-1]["detail"] == "Found online: the town of 1 of 1 jobs"

    # Switched off: it comes back, labelled, and nothing is looked up again.
    manager.reapply(run.id, [ConditionEdit(text="only big cities", original=0, use=False)])
    cards = wait_until_done(manager)["result"]["jobs"]["cards"]
    pcb = next(c for c in cards if c["title"] == "PCB Designer")
    assert pcb["location"] == "Garching" and pcb["location_found_online"]
    assert len(ai.looked_up) == 1
