"""Travel limits to reference places: "at most 50 minutes by public transport to a city with at
least 0.3% of the country's people". The owner's example: a job in Fürstenfeldbruck fits through
Munich, although Fürstenfeldbruck itself is small.

Google Maps is always a fake here; nothing contacts the real service."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_location_conditions import ScriptedClient
from test_search import ready  # noqa: F401

from jobcu import places, travel
from jobcu.dedupe import JobGroup
from jobcu.filters import condition_fit
from jobcu.keystore import KeyStore
from jobcu.location import (
    Anchor,
    CheckedCondition,
    Condition,
    ConditionEdit,
    LocationPlan,
    SortedAnchor,
    SortedCondition,
    TownRef,
    apply_edits,
    check_conditions,
)
from jobcu.pipeline import build_card
from jobcu.settings import Settings
from jobcu.sources.base import FoundJob
from jobcu.sources.http import PoliteClient
from jobcu.travel import TravelGuess, TravelGuesses, TravelMeter

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
OWNERS_TEXT = "at most 50 minutes to a city with at least 0.3% of the country's people"


def near(minutes=50, share=0.003, **extra):
    return Condition(text=OWNERS_TEXT, understood_as="Within 50 minutes of a big city",
                     status="estimate", kind="near", max_minutes=minutes, travel_mode="transit",
                     anchor=Anchor(description="cities with at least 0.3%",
                                   min_share_of_country=share), **extra)


def group(location, job_id="1", company="FakeCo", latitude=None, longitude=None):
    return JobGroup(copies=[FoundJob(
        source="s", source_job_id=job_id, url=f"https://jobs.test/{job_id}", title="Engineer",
        company=company, location_text=location, country="DE", latitude=latitude,
        longitude=longitude, posted_at=NOW, date_precision="exact")])


class FakeMaps:
    """Answers route matrices with made-up minutes per destination town, and company look-ups."""

    def __init__(self, minutes, company=None):
        self.minutes = minutes  # {town name: minutes}
        self.company = company
        self.requests = []

    def handler(self, request):
        body = json.loads(request.content)
        self.requests.append((request.url.path, body, dict(request.headers)))
        if request.url.host == "places.googleapis.com":
            return httpx.Response(200, json={"places": [{"location": self.company}]}
                                  if self.company else {})
        elements = []
        for index, destination in enumerate(body["destinations"]):
            point = destination["waypoint"]["location"]["latLng"]
            town = min(places.towns_in("DE"), key=lambda t: places.km(
                t.latitude, t.longitude, point["latitude"], point["longitude"]))
            minutes = self.minutes.get(town.name)
            elements.append({"originIndex": 0, "destinationIndex": index,
                             **({"duration": f"{minutes * 60}s", "condition": "ROUTE_EXISTS"}
                                if minutes is not None else {"condition": "ROUTE_NOT_FOUND"})})
        return httpx.Response(200, json=elements)


def meter(fake=None, key=True, client=None, settings=None, notes=None):
    keys = KeyStore()
    if key:
        keys.set(travel.KEY_NAME, "fake-maps-key")
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(fake.handler if fake else _no_network))
    return TravelMeter(client, keys, http, settings or Settings(),
                       note=(notes.append if notes is not None else lambda m: None),
                       now=lambda: NOW)


def _no_network(request):
    raise AssertionError("Google Maps must not be asked here")


# --- Reading the sentence -----------------------------------------------------------------


def test_the_owners_sentence_is_one_condition_with_a_reference_point():
    sorted_kinds = {OWNERS_TEXT: SortedCondition(
        text=OWNERS_TEXT, understood_as="Within 50 minutes by public transport of a big city",
        kind="near", max_minutes=50, travel_mode="transit",
        anchor=SortedAnchor(description="cities with at least 0.3% of the people",
                            min_share_of_country=0.003))}
    client = ScriptedClient(None, sorted_kinds=sorted_kinds)
    (condition,) = check_conditions(client, [OWNERS_TEXT], ["DE", "IE"])
    assert condition.kind == "near" and condition.max_minutes == 50
    assert condition.anchor.min_share_of_country == 0.003 and condition.filters
    assert client.research_calls == []  # sizes need no web look-up


def test_reference_places_that_must_be_looked_up_are_researched():
    text = "at most 30 minutes by car from a university town"
    sorted_kinds = {text: SortedCondition(
        text=text, understood_as="Within 30 minutes by car of a university town", kind="near",
        max_minutes=30, travel_mode="drive",
        anchor=SortedAnchor(description="a university town", needs_the_web=True))}
    answer = CheckedCondition(understood_as="University towns", kind="towns_that_fit",
                              towns=[TownRef(name="Freising", country="DE")],
                              confidence="checked", note="From the universities' list.")
    client = ScriptedClient(answer, sorted_kinds=sorted_kinds)
    (condition,) = check_conditions(client, [text], ["DE"])
    assert condition.kind == "near" and condition.travel_mode == "drive"
    assert [t.name for t in condition.anchor.researched] == ["Freising"]
    assert condition.sources and len(client.research_calls) == 1


def test_reference_places_of_a_size_come_from_the_town_list():
    towns = {town.name for town in travel.anchor_towns(near().anchor, "DE")}
    assert "Munich" in towns and "Fürstenfeldbruck" not in towns
    both = Anchor(min_people=100_000, named=[TownRef(name="Freising", country="DE"),
                                             TownRef(name="Augsburg", country="DE")])
    assert [t.name for t in travel.anchor_towns(both, "DE")] == ["Augsburg"]


# --- Measuring ----------------------------------------------------------------------------


def test_fuerstenfeldbruck_fits_through_munich():
    fake = FakeMaps({"Munich": 17, "Augsburg": 55})
    condition = near()
    job = group("Fürstenfeldbruck, Fürstenfeldbruck (Kreis)")
    meter(fake).measure([condition], [job], [0])
    assert condition_fit(condition, job) == "yes"
    (path, body, headers), = fake.requests
    assert path.endswith("computeRouteMatrix") and body["travelMode"] == "TRANSIT"
    assert headers["x-goog-api-key"] == "fake-maps-key"
    assert body["departureTime"] == "2026-09-22T06:00:00Z"  # Tuesday, 8 in the morning
    assert condition.status == "applied"  # measured, not estimated
    card = build_card(job, job_id=1, is_new=True, state=None, scored=None,
                      plan=LocationPlan(text="", understood_as="", countries=["DE"], places=[],
                                        conditions=[condition], not_checked_yet=[],
                                        outside_supported_area=[], broad=False),
                      source_names={"s": "Board"}, possible_duplicate_of=None, started_at=NOW,
                      posted_within_hours=24)
    check = card["location_checks"][-1]
    assert check["status"] == "verified" and check["source"] == "Google Maps"
    assert check["detail"] == "Munich, 17 min by public transport"


def test_clear_cases_need_no_route_look_up():
    condition = near(minutes=10)
    in_munich = group("München", "1")
    far_away = group("Garmisch-Partenkirchen", "2")  # no big city within 10 minutes' reach
    meter().measure([condition], [in_munich, far_away], [0, 1])
    assert condition_fit(condition, in_munich) == "yes"
    assert condition_fit(condition, far_away) == "no"
    assert travel.detail(condition, far_away)[0].startswith("nearest is Munich")


def test_a_job_just_over_the_limit_is_measured_from_the_company_address():
    fake = FakeMaps({"Munich": 55}, company={"latitude": 48.20, "longitude": 11.40})
    condition = near()
    job = group("Fürstenfeldbruck", company="Close To Munich GmbH")
    meter(fake).measure([condition], [job], [0])
    hosts = [path for path, _, _ in fake.requests]
    assert hosts[1].endswith("places:searchText") and len(hosts) == 3
    assert "Close To Munich GmbH, Fürstenfeldbruck" in fake.requests[1][1]["textQuery"]
    assert condition.travel["s:1"]["from"] == "company"


def test_without_a_key_the_ai_estimates_and_says_so():
    class GuessingClient:
        def __init__(self):
            self.prompts = []

        def generate(self, output, **request):
            self.prompts.append(request["prompt"])
            return TravelGuesses(answers=[TravelGuess(id="P0", town="Munich", minutes=25)])

    client, notes = GuessingClient(), []
    condition = near()
    job = group("Fürstenfeldbruck")
    meter(key=False, client=client, notes=notes).measure([condition], [job], [0])
    assert condition_fit(condition, job) == "yes" and condition.status == "estimate"
    assert "Fürstenfeldbruck" in client.prompts[0] and "Munich" in client.prompts[0]
    assert travel.detail(condition, job)[1] == "AI estimate"


def test_the_monthly_limit_stops_google_maps_and_the_ai_takes_over():
    class GuessingClient:
        def generate(self, output, **request):
            return TravelGuesses(answers=[TravelGuess(id="P0", town="Munich", minutes=70)])

    settings = Settings()
    settings.limits.maps_monthly_routes = 0
    notes = []
    condition = near()
    job = group("Fürstenfeldbruck")
    meter(client=GuessingClient(), settings=settings, notes=notes).measure([condition], [job], [0])
    assert condition_fit(condition, job) == "no"
    assert any("used up" in note for note in notes)


def test_a_corrected_limit_needs_no_new_look_up():
    fake = FakeMaps({"Munich": 17, "Augsburg": 55})
    condition = near()
    job = group("Fürstenfeldbruck")
    plan = LocationPlan(text="", understood_as="", countries=["DE"], places=[],
                        conditions=[condition], not_checked_yet=[], outside_supported_area=[],
                        broad=False)
    meter(fake).measure([condition], [job], [0])
    stricter = apply_edits(ScriptedClient(None), plan,
                           [ConditionEdit(text=OWNERS_TEXT, original=0, max_minutes=15)])
    corrected = stricter.conditions[0]
    meter().measure([corrected], [job], [0])  # would fail if Google Maps were asked again
    assert condition_fit(corrected, job) == "no" and corrected.changed_by_you
    # Another way of travelling means the old times don't apply any more.
    by_car = apply_edits(ScriptedClient(None), plan,
                         [ConditionEdit(text=OWNERS_TEXT, original=0, travel_mode="drive")])
    assert by_car.conditions[0].travel == {}


def test_job_sites_coordinates_come_first():
    job = group("Somewhere", latitude=48.18, longitude=11.25)
    point = travel.job_point(job)
    assert (point.latitude, point.longitude, point.how) == (48.18, 11.25, "address")
    assert travel.job_point(group("Fürstenfeldbruck")).how == "town"


@pytest.mark.parametrize(("country", "expected"), [
    ("DE", "2026-09-22T06:00:00Z"), ("GB", "2026-09-22T07:00:00Z"),
    ("FI", "2026-09-22T05:00:00Z"),
])
def test_departure_is_a_weekday_morning_local_time(country, expected):
    assert travel.departure(country, NOW) == expected
    monday_night = NOW + timedelta(days=1, hours=12)  # Tuesday 22:00 local → next Tuesday
    assert travel.departure("DE", monday_night) == "2026-09-29T06:00:00Z"


def test_a_distance_limit_is_measured_in_a_straight_line():
    condition = Condition(text="within 30 km of Munich", understood_as="Within 30 km of Munich",
                          status="applied", kind="near", max_km=30,
                          anchor=Anchor(named=[TownRef(name="Munich", country="DE")]))
    assert condition_fit(condition, group("Fürstenfeldbruck")) == "yes"
    assert condition_fit(condition, group("Augsburg")) == "no"


def test_testing_the_key_explains_problems_plainly():
    def refused(request):
        return httpx.Response(403, json={"error": {"message": "API key not valid"}})

    keys = KeyStore()
    assert travel.check_key(keys, None)[1] == "Please save a Google Maps key first."
    keys.set(travel.KEY_NAME, "wrong-key")
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(refused))
    ok, message = travel.check_key(keys, http)
    assert not ok and "didn't accept the key" in message


# --- A whole search -----------------------------------------------------------------------


def test_a_search_keeps_jobs_near_a_big_city_and_leaves_out_far_ones(ready, monkeypatch):  # noqa: F811
    import re

    from test_search import FakeAI, wait_until_done

    from jobcu import search
    from jobcu.ai.base import RawReply, Usage
    from jobcu.settings import SearchForm
    from jobcu.sources.base import JobSource

    class NearAI(FakeAI):
        def complete_json(self, **request):
            name, prompt = request["schema_name"], request["prompt"]
            if name == "LocationUnderstanding":
                answer = {"understood_as": "Germany, near a big city.", "limits_countries": True,
                          "countries": ["DE"], "places": [],
                          "conditions_about_places": [OWNERS_TEXT],
                          "conditions_about_the_job": [], "outside_supported_area": []}
            elif name == "SortedConditions":
                answer = {"conditions": [{
                    "text": OWNERS_TEXT, "understood_as": "Within 50 minutes of a big city",
                    "kind": "near", "max_minutes": 50, "travel_mode": "transit",
                    "anchor": {"description": "big cities", "min_share_of_country": 0.003}}]}
            elif name == "TravelGuesses":
                answer = {"answers": [
                    {"id": pid, "town": "Munich" if "Fürstenfeldbruck" in line else "Nuremberg",
                     "minutes": 25 if "Fürstenfeldbruck" in line else 95}
                    for pid, line in re.findall(r"^(P\d+) \| (.*)$", prompt, re.MULTILINE)]}
            else:
                return super().complete_json(**request)
            return RawReply(json.dumps(answer), Usage(10, 5))

    class PlacedSource(JobSource):
        id, name, kind = "placed", "Placed Jobs", "job_board"

        def search(self, query, ctx):
            for i, place in enumerate(["Fürstenfeldbruck", "Hof", "München"]):
                yield FoundJob(source="placed", source_job_id=str(i), url=f"https://jobs.test/{i}",
                               title="Hardware Engineer", company=f"Company {i}",
                               location_text=place, country="DE",
                               posted_at=datetime.now(UTC), date_precision="exact",
                               description="Full ad", description_is_complete=True)

    monkeypatch.setattr("jobcu.ai.client.AIClient.adapter", lambda self: NearAI())
    monkeypatch.setattr("jobcu.pipeline.all_sources", lambda: [PlacedSource()])
    manager = search.SearchManager()
    manager.start(SearchForm(location_text="Germany, " + OWNERS_TEXT))
    result = wait_until_done(manager)
    assert result["status"] == "finished", result["error"]
    jobs = result["result"]["jobs"]
    assert sorted(card["location"] for card in jobs["cards"]) == ["Fürstenfeldbruck", "München"]
    assert [card["location"] for card in jobs["ruled_out_by_conditions"]] == ["Hof"]
    bruck = next(card for card in jobs["cards"] if card["location"] == "Fürstenfeldbruck")
    check = bruck["location_checks"][-1]
    assert check["detail"] == "Munich, 25 min by public transport"
    assert check["source"] == "AI estimate"
    assert any("Google Maps key" in note for note in result["notes"])
