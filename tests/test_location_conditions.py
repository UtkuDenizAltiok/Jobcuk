"""Conditions in the location text: researched on the web, computed, or shown as not checked.

The owner's own examples: "a city with at least 0.3% of the country's people", "cities where
far-right parties are below the national average", "shops open on Sunday".
"""

from datetime import UTC, datetime

import pytest

from jobcu.ai.base import AIError, ResearchReply, Source, Usage
from jobcu.dedupe import group_duplicates
from jobcu.filters import apply_rules, condition_fit
from jobcu.location import (
    CheckedCondition,
    Condition,
    LocationPlan,
    PlaceRegion,
    RegionAnswer,
    SortedCondition,
    SortedConditions,
    TownRef,
    check_conditions,
    fits,
    smallest_town,
)
from jobcu.sources.base import FoundJob

NOW = datetime.now(UTC)


class ScriptedClient:
    """Stands in for the AI: it sorts the conditions, then answers each research call."""

    def __init__(self, answer, sorted_kinds=None, notes="Notes from the web.", sources=None,
                 fail=None):
        self.answer = answer
        self.sorted_kinds = sorted_kinds  # {condition text: SortedCondition}
        self.notes = notes
        self.sources = sources or [Source("https://example.test/a", "Statistics office")]
        self.fail = fail
        self.research_calls = []
        self.generate_calls = []

    def research(self, **request):
        self.research_calls.append(request)
        if self.fail:
            raise self.fail
        return ResearchReply(self.notes, self.sources, Usage(100, 100, web_searches=2))

    def generate(self, output, **request):
        self.generate_calls.append(request)
        if output is SortedConditions:
            texts = [line.removeprefix("- ") for line in request["prompt"].splitlines()
                     if line.startswith("- ")]
            return SortedConditions(conditions=[
                (self.sorted_kinds or {}).get(text)
                or SortedCondition(text=text, understood_as=text, kind="needs_the_web")
                for text in texts
            ])
        return self.answer


def job(title="Hardware Engineer", location="Garching bei München", country="DE"):
    found = FoundJob(source="s", source_job_id="1", url="https://x.test/1", title=title,
                     company="Acme", location_text=location, country=country,
                     posted_at=NOW, date_precision="exact")
    return group_duplicates([found], {"s": "job_board"})[0]


# --- Conditions about how big a town is (computed from Jobcu's own figures) -------------


def test_a_town_size_condition_is_computed_per_country():
    condition = Condition(text="at least 0.3% of the country's people",
                          understood_as="Towns with at least 0.3% of the country's people",
                          status="applied", kind="town_size", min_share_of_country=0.003)
    # 0.3% is about 250,000 people in Germany and about 16,000 in Ireland (DECISIONS.md).
    assert 245_000 < smallest_town(condition, "DE") < 255_000
    assert 15_000 < smallest_town(condition, "IE") < 17_000
    assert fits(condition, "DE", "München") == "yes"
    assert fits(condition, "DE", "Garching bei München") == "no"
    assert fits(condition, "IE", "Galway") == "yes"  # big enough for Ireland
    assert fits(condition, "DE", "Somewhere unknown") == "unknown"


def test_towns_to_avoid_and_towns_that_fit():
    avoid = Condition(text="no far-right cities", understood_as="Not cities where the far right "
                      "is above the national average", status="applied", kind="towns_to_avoid",
                      towns=[TownRef(name="Dresden", country="DE")])
    assert fits(avoid, "DE", "Dresden") == "no"
    assert fits(avoid, "DE", "München") == "yes"
    assert fits(avoid, "DE", "A village nobody lists") == "yes"  # a town, and not Dresden
    # Only a country or a region: the job may still be in Dresden.
    assert fits(avoid, "DE", "Deutschland") == "unknown"
    assert fits(avoid, "DE", "Sachsen") == "unknown"
    assert fits(avoid, "DE", None) == "unknown"

    only = Condition(text="shops open on Sunday", understood_as="Towns with Sunday opening",
                     status="estimate", kind="towns_that_fit",
                     towns=[TownRef(name="Berlin", country="DE")])
    assert fits(only, "DE", "Berlin, Germany") == "yes"
    assert fits(only, "DE", "München") == "no"
    assert fits(only, "DE", "A village nobody lists") == "unknown"


SAXONY = PlaceRegion(code="DE.13", name="Saxony", country="DE")


def test_a_whole_region_decides_its_small_towns_except_the_ones_named():
    # Search 8: Radeberg (Landkreis Bautzen, Saxony) passed because no list of towns names it.
    avoid = Condition(text="no far-right cities", understood_as="Not where the far right is "
                      "above the national average", status="applied", kind="towns_to_avoid",
                      towns=[TownRef(name="Gelsenkirchen", country="DE")], regions=[SAXONY],
                      exceptions=[TownRef(name="Leipzig", country="DE")])
    assert fits(avoid, "DE", "Radeberg, Bautzen (Kreis)") == "no"
    assert fits(avoid, "DE", "Dresden") == "no"
    assert fits(avoid, "DE", "Leipzig") == "yes"  # the exception
    assert fits(avoid, "DE", "Gelsenkirchen") == "no" and fits(avoid, "DE", "München") == "yes"
    assert fits(avoid, "DE", "Sachsen") == "no"  # only the region is known, and it's avoided
    assert fits(avoid, "DE", "Deutschland") == "unknown"
    # Nothing to avoid in Ireland: every Irish town is fine, but a bare country still isn't a town.
    assert fits(avoid, "IE", "Cork") == "yes" and fits(avoid, "IE", "Ireland") == "unknown"

    fit = Condition(text="in the east", understood_as="Eastern states", status="applied",
                    kind="towns_that_fit", regions=[SAXONY])
    assert fits(fit, "DE", "Radeberg") == "yes" and fits(fit, "DE", "München") == "no"


def test_regions_in_the_answer_are_kept_and_unknown_ones_are_named():
    answer = CheckedCondition(
        understood_as="Places where the AfD was above its national share are left out",
        kind="towns_to_avoid", towns=[TownRef(name="Gelsenkirchen", country="DE")],
        regions=[RegionAnswer(name="Sachsen", country="DE"),
                 RegionAnswer(name="Landkreis Bautzen", country="DE"),
                 RegionAnswer(name="Atlantis", country="DE"),
                 RegionAnswer(name="Wales", country="GB")],  # not a country searched
        exceptions=[TownRef(name="Leipzig", country="DE")],
        confidence="checked", note="From the 2025 federal election results.")
    (condition,) = check_conditions(ScriptedClient(answer), ["no far-right cities"], ["DE"])
    assert [(r.code, r.name) for r in condition.regions] == [
        ("DE.13", "Saxony"), ("DE.K.14625", "Landkreis Bautzen")]
    assert [t.name for t in condition.exceptions] == ["Leipzig"]
    assert "doesn't know Atlantis as a region" in condition.note

    only_regions = answer.model_copy(update={"towns": [], "regions": answer.regions[:1]})
    (condition,) = check_conditions(ScriptedClient(only_regions), ["no far-right cities"], ["DE"])
    assert condition.status == "applied" and condition.kind == "towns_to_avoid"


def test_conditions_that_could_not_be_checked_never_rule_a_job_out():
    unchecked = Condition(text="nice weather", understood_as="nice weather",
                          status="not_checked", kind="could_not_check")
    assert fits(unchecked, "DE", "München") == "unknown"


# --- Researching a condition ------------------------------------------------------------


def test_a_condition_is_researched_and_turned_into_towns_to_avoid():
    answer = CheckedCondition(
        understood_as="Cities where the AfD was above its national share are left out",
        kind="towns_to_avoid", towns=[TownRef(name="Dresden", country="DE")],
        confidence="checked", note="From the 2025 federal election results.")
    client = ScriptedClient(answer)
    conditions = check_conditions(client, ["no far-right cities"], ["DE"])
    assert len(conditions) == 1
    condition = conditions[0]
    assert condition.status == "applied" and condition.kind == "towns_to_avoid"
    assert [town.name for town in condition.towns] == ["Dresden"]
    assert condition.sources[0].url == "https://example.test/a"
    assert "Germany" in client.research_calls[0]["prompt"]


def test_an_estimate_is_labelled_and_an_unanswerable_condition_is_not_checked():
    guess = CheckedCondition(understood_as="Towns within 50 minutes of a big city",
                             kind="towns_that_fit", towns=[TownRef(name="Garching", country="DE")],
                             confidence="estimate", note="Judged from the map, not measured.")
    assert check_conditions(ScriptedClient(guess), ["50 minutes to a city"], ["DE"])[0].status == (
        "estimate"
    )

    empty = CheckedCondition(understood_as="Towns with Turkish supermarkets",
                             kind="towns_that_fit", towns=[], confidence="checked",
                             note="Couldn't find a reliable list.")
    assert check_conditions(ScriptedClient(empty), ["Turkish shops"], ["DE"])[0].status == (
        "not_checked"
    )

    failing = ScriptedClient(empty, fail=AIError("This provider can't search the web."))
    condition = check_conditions(failing, ["Turkish shops"], ["DE"])[0]
    assert condition.status == "not_checked" and "can't search" in condition.note


def test_a_size_condition_is_worked_out_without_looking_anything_up():
    sorted_kinds = {"a city with at least 0.3% of the country's people": SortedCondition(
        text="a city with at least 0.3% of the country's people",
        understood_as="Towns with at least 0.3% of the country's people",
        kind="town_size", min_share_of_country=0.003)}
    client = ScriptedClient(None, sorted_kinds=sorted_kinds)
    condition = check_conditions(
        client, ["a city with at least 0.3% of the country's people"], ["DE", "IE"])[0]
    assert not client.research_calls  # no web look-up needed
    assert condition.status == "applied" and condition.kind == "town_size"
    assert condition.min_share_of_country == 0.003
    assert fits(condition, "DE", "München") == "yes"
    assert fits(condition, "DE", "Garching bei München") == "no"


def test_a_condition_about_the_job_is_shown_but_not_used_for_places():
    sorted_kinds = {"no agencies": SortedCondition(
        text="no agencies", understood_as="No staffing agencies", kind="about_the_job")}
    condition = check_conditions(ScriptedClient(None, sorted_kinds=sorted_kinds),
                                 ["no agencies"], ["DE"])[0]
    assert condition.kind == "about_job" and condition.status == "not_checked"
    assert fits(condition, "DE", "München") == "unknown"


def test_only_a_few_conditions_are_researched_per_search():
    answer = CheckedCondition(understood_as="x", kind="towns_to_avoid",
                              towns=[TownRef(name="Dresden", country="DE")], confidence="checked",
                              note="")
    client = ScriptedClient(answer)
    conditions = check_conditions(client, [f"condition {i}" for i in range(6)], ["DE"])
    assert len(conditions) == 6
    assert len(client.research_calls) == 4
    assert [c.status for c in conditions[4:]] == ["not_checked", "not_checked"]


# --- What the search does with them ------------------------------------------------------


def plan_with(condition):
    return LocationPlan(text="…", understood_as="…", countries=["DE"], places=[],
                        conditions=[condition], not_checked_yet=[], outside_supported_area=[],
                        broad=False)


def test_jobs_that_fail_a_condition_are_left_out_and_counted():
    condition = Condition(text="big cities only", understood_as="Towns with at least 250,000 "
                          "people", status="applied", kind="town_size", min_people=250_000)
    groups = [job(location="München"), job(location="Garching bei München"),
              job(location="Somewhere unknown")]
    outcome = apply_rules(groups, [None, None, None], started_at=NOW, posted_within_hours=24,
                          job_types=["full_time_permanent", "fixed_term", "part_time",
                                     "internship_or_working_student", "freelance_or_contract"],
                          exclude_remote=False, countries=["DE"], conditions=[condition])
    assert outcome.kept == [0, 2]  # the unknown place is kept, not silently dropped
    assert outcome.left_out["location_condition"] == 1
    # The jobs a condition ruled out are remembered, so the screen can show them back.
    assert outcome.by_reason["location_condition"] == [1]
    assert condition_fit(condition, groups[1]) == "no"
    assert condition_fit(condition, groups[2]) == "unknown"


def test_the_card_says_what_each_condition_found():
    from jobcu.pipeline import build_card

    condition = Condition(text="big cities only", understood_as="Towns with at least 250,000 "
                          "people", status="applied", kind="town_size", min_people=250_000)
    card = build_card(job(location="München"), job_id=1, is_new=True, state=None, scored=None,
                      plan=plan_with(condition), source_names={"s": "Board"},
                      possible_duplicate_of=None, started_at=NOW, posted_within_hours=24)
    labels = {check["label"]: check for check in card["location_checks"]}
    assert labels["Towns with at least 250,000 people"]["status"] == "verified"
    assert labels["Towns with at least 250,000 people"]["source"] == "Worked out by Jobcu"

    unclear = build_card(job(location="Nowhere at all"), job_id=2, is_new=True, state=None,
                         scored=None, plan=plan_with(condition), source_names={"s": "Board"},
                         possible_duplicate_of=None, started_at=NOW, posted_within_hours=24)
    assert any(check["status"] == "unclear" for check in unclear["location_checks"])


@pytest.mark.parametrize("country,expected", [("DE", 250_500), ("IE", 15_930)])
def test_the_owners_example_thresholds(country, expected):
    condition = Condition(text="0.3%", understood_as="0.3%", status="applied", kind="town_size",
                          min_share_of_country=0.003)
    assert smallest_town(condition, country) == expected


def test_scoring_still_hears_about_conditions_jobcu_could_not_apply():
    from jobcu.scoring import _background

    plan = plan_with(Condition(text="no staffing agencies", understood_as="No staffing agencies",
                               status="not_checked", kind="about_job"))
    plan.conditions.append(Condition(
        text="towns with Turkish supermarkets", understood_as="Towns with Turkish supermarkets",
        status="not_checked", kind="could_not_check"))
    plan.conditions.append(Condition(
        text="big cities", understood_as="Towns with at least 250,000 people", status="applied",
        kind="town_size", min_people=250_000))
    from jobcu.profile import Profile
    profile = Profile.model_validate({
        "summary": "x", "current_or_last_role": None, "field": "Electronics", "skills": [],
        "technical_areas": [], "years_full_time_experience": 0,
        "years_student_or_part_time_experience": 0, "experience_note": "", "seniority": "junior",
        "education": [], "languages": [], "target_roles": [], "target_fields": [],
        "preferences": [], "work_mode_preference": "not_stated", "dealbreakers": [],
        "work_authorisation": None, "ignored_as_application_specific": [],
    })
    background = _background(profile, plan)
    assert "No staffing agencies" in background
    assert "Towns with Turkish supermarkets" in background
    # The size condition is already applied when filtering, so scoring isn't asked to judge it.
    assert "250,000" not in background
