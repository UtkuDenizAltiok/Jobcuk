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
    """Answers route matrices with made-up minutes per destination town."""

    def __init__(self, minutes):
        self.minutes = minutes  # {town name: minutes}
        self.requests = []

    def handler(self, request):
        body = json.loads(request.content)
        self.requests.append((request.url.path, body, dict(request.headers)))
        if "departureTime" in body and body["travelMode"] != "TRANSIT" and "routingPreference" \
                not in body:
            # What the real Routes API answers (checked 2026-09-22).
            return httpx.Response(400, json=[{"error": {
                "code": 400, "status": "INVALID_ARGUMENT",
                "message": "Timestamp cannot be set for TRAFFIC_UNAWARE routing mode."}}])
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


def test_car_trips_are_measured_without_a_departure_time():
    fake = FakeMaps({"Munich": 25})
    condition = near(minutes=30)
    condition.travel_mode = "drive"
    job = group("Fürstenfeldbruck")
    notes = []
    meter(fake, notes=notes).measure([condition], [job], [0])
    (_, body, _), = fake.requests
    assert body["travelMode"] == "DRIVE" and "departureTime" not in body
    assert condition_fit(condition, job) == "yes" and notes == []
    assert travel.detail(condition, job) == ("Munich, 25 min by car", "Google Maps")


def test_google_s_own_words_go_to_the_log_when_it_refuses(caplog):
    def refuse(request):
        return httpx.Response(400, json=[{"error": {"code": 400, "message": "Bad field."}}])

    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(refuse))
    with caplog.at_level("WARNING"), pytest.raises(travel.MapsError, match="code 400"):
        travel.GoogleMaps("fake-maps-key", http, now=lambda: NOW).minutes(
            travel.job_point(group("Freising")), [places.find("Munich", "DE")], "transit")
    assert "Google Maps answered 400: Bad field." in caplog.text


def test_google_s_daily_limit_is_named_as_such(caplog):
    def used_up(request):
        return httpx.Response(429, json=[{"error": {"code": 429, "message":
            "Quota exceeded for quota metric 'Route Matrix Elements' and limit 'Route matrix "
            "elements per day' of service 'routes.googleapis.com'."}}])

    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(used_up))
    with caplog.at_level("WARNING"), pytest.raises(travel.MapsError, match="daily limit"):
        travel.GoogleMaps("fake-maps-key", http, now=lambda: NOW).minutes(
            travel.job_point(group("Freising")), [places.find("Munich", "DE")], "transit")
    assert "elements per day" in caplog.text


def test_clear_cases_need_no_route_look_up():
    condition = near(minutes=10)
    in_munich = group("München", "1")
    far_away = group("Garmisch-Partenkirchen", "2")  # no big city within 10 minutes' reach
    meter().measure([condition], [in_munich, far_away], [0, 1])
    assert condition_fit(condition, in_munich) == "yes"
    assert condition_fit(condition, far_away) == "no"
    assert travel.detail(condition, far_away)[0].startswith("nearest is Munich")


def test_a_close_call_is_measured_from_the_ads_own_place_only():
    # A company can have several sites with the same name, so Jobcu never looks up a company's
    # address elsewhere: the place the ad names is what counts (the owner's decision).
    fake = FakeMaps({"Munich": 52})
    condition = near()
    job = group("Fürstenfeldbruck", company="Has Many Sites GmbH")
    meter(fake).measure([condition], [job], [0])
    assert [path for path, _, _ in fake.requests] == ["/distanceMatrix/v2:computeRouteMatrix"]
    assert condition_fit(condition, job) == "no"
    assert travel.detail(condition, job)[0] == "Munich, 52 min by public transport"


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


# --- Remembered for 30 days ---------------------------------------------------------------


def test_googles_travel_times_are_never_kept_beyond_the_search():
    # The Routes API terms (19.3) allow keeping coordinates only, so the next search asks again.
    fake = FakeMaps({"Munich": 17, "Augsburg": 55})
    meter(fake).measure([near()], [group("Fürstenfeldbruck", "1")], [0])
    meter(fake).measure([near()], [group("Fürstenfeldbruck", "2")], [0])
    assert len(fake.requests) == 2
    from jobcu import db
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM travel_memory").fetchone()[0] == 0


def test_ai_estimates_are_remembered_for_30_days_from_the_same_town():
    class GuessingClient:
        calls = 0

        def generate(self, output, **request):
            GuessingClient.calls += 1
            return TravelGuesses(answers=[TravelGuess(id="P0", town="Munich", minutes=25)])

    meter(key=False, client=GuessingClient()).measure([near()], [group("Fürstenfeldbruck")], [0])
    later = near()
    job = group("Fürstenfeldbruck", "2", company="Other GmbH")
    meter(key=False, client=GuessingClient()).measure([later], [job], [0])
    assert GuessingClient.calls == 1 and condition_fit(later, job) == "yes"
    stale = TravelMeter(GuessingClient(), KeyStore(), None, Settings(),
                        now=lambda: NOW + timedelta(days=31))
    stale.measure([near()], [job], [0])
    assert GuessingClient.calls == 2


def test_estimates_are_remembered_only_until_there_is_a_key():
    class GuessingClient:
        calls = 0

        def generate(self, output, **request):
            GuessingClient.calls += 1
            return TravelGuesses(answers=[TravelGuess(id="P0", town="Munich", minutes=25)])

    meter(key=False, client=GuessingClient()).measure([near()], [group("Fürstenfeldbruck")], [0])
    meter(key=False, client=GuessingClient()).measure([near()], [group("Fürstenfeldbruck")], [0])
    assert GuessingClient.calls == 1  # the second search used the remembered estimate
    fake = FakeMaps({"Munich": 17, "Augsburg": 55})
    with_key = near()
    meter(fake).measure([with_key], [group("Fürstenfeldbruck")], [0])
    assert len(fake.requests) == 1 and travel.detail(with_key, group("Fürstenfeldbruck")) == (
        "Munich, 17 min by public transport", "Google Maps")


# --- Reference places defined by any fact -------------------------------------------------


def test_places_that_fail_a_fact_are_never_reference_places():
    anchor = Anchor(min_share_of_country=0.003, avoided=[TownRef(name="Dresden", country="DE")],
                    looked_up=True)
    towns = {town.name for town in travel.anchor_towns(anchor, "DE")}
    assert "Leipzig" in towns and "Dresden" not in towns


def test_one_fact_is_looked_up_once_for_the_job_town_and_the_reference_places():
    far_right = "no cities where far-right parties polled above the national average"
    commute = "at most 50 minutes by public transport to a city with at least 0.3% of people"
    sorted_kinds = {
        commute: SortedCondition(
            text=commute, understood_as="Within 50 minutes of a big city that isn't a "
            "far-right stronghold", kind="near", max_minutes=50, travel_mode="transit",
            anchor=SortedAnchor(description="big cities that aren't far-right strongholds",
                                min_share_of_country=0.003, needs_the_web=True,
                                look_up=far_right)),
        far_right: SortedCondition(text=far_right, understood_as="Not in far-right strongholds",
                                   kind="needs_the_web"),
    }
    avoid = CheckedCondition(understood_as="Avoid far-right strongholds", kind="towns_to_avoid",
                             towns=[TownRef(name="Dresden", country="DE"),
                                    TownRef(name="Chemnitz", country="DE")],
                             confidence="checked", note="Federal election 2025 results.")
    client = ScriptedClient(avoid, sorted_kinds=sorted_kinds)
    reference, own_town = check_conditions(client, [commute, far_right], ["DE"])
    assert len(client.research_calls) == 1
    assert [t.name for t in reference.anchor.avoided] == ["Dresden", "Chemnitz"]
    assert reference.anchor.min_share_of_country == 0.003 and reference.sources
    assert own_town.kind == "towns_to_avoid" and own_town.text == far_right


def test_a_fact_given_in_fewer_words_is_the_other_condition_s_fact():
    # The owner's own sentence (2026-09-22): the travel condition's reference places were looked
    # up from the part in brackets alone, which the AI read as turnout.
    far_right = ("I dont want far-right fascist supporter cities (the elections voting ratio "
                 "should be less than its country average)")
    commute = "at most 50 minutes by car to a city that has at least %0.3 of its country's people"
    sorted_kinds = {
        commute: SortedCondition(
            text=commute, understood_as="Within 50 minutes by car of such a city", kind="near",
            max_minutes=50, travel_mode="drive",
            anchor=SortedAnchor(description="big cities", min_share_of_country=0.003,
                                needs_the_web=True, look_up="the elections voting ratio should "
                                "be less than its country average")),
        far_right: SortedCondition(text=far_right, understood_as="Not far-right cities",
                                   kind="needs_the_web"),
    }
    avoid = CheckedCondition(understood_as="Avoid far-right strongholds", kind="towns_to_avoid",
                             towns=[TownRef(name="Görlitz", country="DE")], confidence="checked",
                             note="AfD above its national share.")
    client = ScriptedClient(avoid, sorted_kinds=sorted_kinds)
    reference, own_town = check_conditions(client, [commute, far_right], ["DE"])
    (call,) = client.research_calls
    assert "far-right fascist supporter cities" in call["prompt"]
    assert reference.anchor.look_up == far_right and own_town.kind == "towns_to_avoid"
    assert [t.name for t in reference.anchor.avoided] == ["Görlitz"]


def test_the_size_still_counts_when_the_fact_about_the_places_can_t_be_checked():
    text = "at most 50 minutes to a big city where far-right parties are weak"
    sorted_kinds = {text: SortedCondition(
        text=text, understood_as="Within 50 minutes of such a city", kind="near",
        max_minutes=50, travel_mode="drive",
        anchor=SortedAnchor(description="big cities", min_share_of_country=0.003,
                            needs_the_web=True, look_up="far-right parties are weak"))}
    nothing = CheckedCondition(understood_as="x", kind="could_not_check", confidence="estimate",
                               note="The notes named no towns.")
    (condition,) = check_conditions(ScriptedClient(nothing, sorted_kinds=sorted_kinds), [text],
                                    ["DE"])
    assert condition.kind == "near" and condition.anchor.min_share_of_country == 0.003
    assert not condition.anchor.looked_up and "couldn't be checked" in condition.note


def test_a_fact_without_a_size_counts_towns_big_enough_to_be_called_cities():
    text = "within 30 minutes of a city that isn't a far-right stronghold"
    sorted_kinds = {text: SortedCondition(
        text=text, understood_as="Within 30 minutes of such a city", kind="near",
        max_minutes=30, travel_mode="transit",
        anchor=SortedAnchor(description="cities that aren't far-right strongholds",
                            needs_the_web=True, look_up="far-right strongholds"))}
    avoid = CheckedCondition(understood_as="x", kind="towns_to_avoid",
                             towns=[TownRef(name="Dresden", country="DE")], confidence="checked",
                             note="")
    (condition,) = check_conditions(ScriptedClient(avoid, sorted_kinds=sorted_kinds), [text],
                                    ["DE"])
    assert condition.anchor.min_people == 20_000 and "20,000" in condition.note


def test_places_to_avoid_can_be_corrected():
    condition = near()
    condition.anchor.avoided = [TownRef(name="Dresden", country="DE"),
                                TownRef(name="Leipzig", country="DE")]
    plan = LocationPlan(text="", understood_as="", countries=["DE"], places=[],
                        conditions=[condition], not_checked_yet=[], outside_supported_area=[],
                        broad=False)
    corrected = apply_edits(ScriptedClient(None), plan, [
        ConditionEdit(text=OWNERS_TEXT, original=0, avoided=["Dresden"])]).conditions[0]
    assert [t.name for t in corrected.anchor.avoided] == ["Dresden"]
    assert corrected.changed_by_you
    assert "Leipzig" in {t.name for t in travel.anchor_towns(corrected.anchor, "DE")}


# --- Facts decided country by country -----------------------------------------------------


def test_a_fact_about_whole_countries_narrows_the_countries_searched():
    from jobcu.location import (
        LocationUnderstanding,
        SortedConditions,
        fits,
        interpret_location,
    )

    text = "a country in the top 10 for work-life balance"

    class CountryClient:
        research_calls = 0

        def generate(self, output, **request):
            if output is LocationUnderstanding:
                return LocationUnderstanding(
                    understood_as="Anywhere, in a top-10 work-life-balance country.",
                    limits_countries=False, countries=[], places=[],
                    conditions_about_places=[text], conditions_about_the_job=[],
                    outside_supported_area=[])
            if output is SortedConditions:
                return SortedConditions(conditions=[SortedCondition(
                    text=text, understood_as="Top-10 countries for work-life balance",
                    kind="needs_the_web")])
            return CheckedCondition(understood_as="Top-10 work-life balance (OECD index)",
                                    kind="countries_that_fit", countries=["NL", "DK", "NO"],
                                    confidence="checked", note="OECD Better Life Index.")

        def research(self, **request):
            CountryClient.research_calls += 1
            from jobcu.ai.base import ResearchReply, Source, Usage
            return ResearchReply("notes", [Source("https://oecd.example/bli", "OECD")],
                                 Usage(1, 1))

    plan = interpret_location(CountryClient(), text)
    assert plan.countries == ["DK", "NL", "NO"] and not plan.broad
    (condition,) = plan.conditions
    assert condition.kind == "countries_that_fit" and condition.status == "applied"
    assert fits(condition, "NL", "Utrecht") == "yes" and fits(condition, "DE", "Berlin") == "no"
    assert CountryClient.research_calls == 1


def test_reference_places_can_be_limited_to_countries_by_a_fact():
    anchor = Anchor(min_people=500_000, countries_fit=["NL"])
    assert travel.anchor_towns(anchor, "DE") == []
    assert {"Amsterdam", "Rotterdam"} <= {t.name for t in travel.anchor_towns(anchor, "NL")}
