"""Arbetsförmedlingen's JobSearch API (Sweden), with made-up answers (never the real site)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import jobtech
from jobcu.sources.base import JobQuery, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)
SWEDEN = ZoneInfo("Europe/Stockholm")


def term(text, language="en", kind="job_title"):
    return SearchTerm(text=text, language=language, kind=kind)


def ad(ad_id, headline, city="Göteborg", hours_ago=1, text="Vi söker en ingenjör.", **extra):
    local = (NOW - timedelta(hours=hours_ago)).astimezone(SWEDEN).replace(tzinfo=None)
    return {
        "id": ad_id, "headline": headline, "removed": False,
        "webpage_url": f"https://arbetsformedlingen.se/platsbanken/annonser/{ad_id}",
        "publication_date": local.isoformat(timespec="seconds"),
        "employer": {"name": "Fake AB"},
        "workplace_address": {"city": city, "municipality": city, "region": "Västra Götalands län",
                              "country": "Sverige", "coordinates": [11.97, 57.71]},
        "employment_type": {"label": "Vanlig anställning"}, "duration": {"label": "Tills vidare"},
        "working_hours_type": {"label": "Heltid"}, "workplace_model": None,
        "application_details": {"url": "https://fake.varbi.com/jobs/1"},
        "description": {"text": text}, **extra,
    }


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("jobtech", "Arbetsförmedlingen"),
                         lambda: False, lambda message: None)


def query(terms, hours=24, places=()):
    return JobQuery(countries=["SE"], places=list(places), terms=terms,
                    posted_within_hours=hours, started_at=NOW)


def test_reads_the_window_and_keeps_the_ads_that_match():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"hits": [
            ad("1", "Elektronikkonstruktör"),
            ad("2", "Hardware Engineer", city="Kista"),
            ad("3", "Undersköterska"),  # a nurse: not what was searched
            ad("4", "Utvecklare", text="Erfarenhet av kraftelektronik och PCB."),  # a field word
            ad("5", "Hardware Engineer", removed=True),
            ad("6", "Hardware Engineer", hours_ago=30),  # older than the window
        ]})

    terms = [term("Hardware Engineer"), term("elektronikkonstruktör", "sv"),
             term("elektronik", "sv", "field_or_skill")]
    jobs = list(jobtech.JobTechSource().search(query(terms), context(handler)))
    assert [job.source_job_id for job in jobs] == ["1", "2", "4"]
    params = requests[0].url.params
    assert params["sort"] == "pubdate-desc" and params["limit"] == "100"
    assert 24 * 60 < int(params["published-after"]) <= 24 * 60 + 10
    assert "description{text}" in requests[0].headers["X-Fields"]  # only the fields Jobcu uses
    kista = jobs[1]
    assert kista.location_text == "Kista, Västra Götalands län" and kista.country == "SE"
    assert kista.description_is_complete and kista.job_types == ["full_time_permanent"]
    assert kista.employer_url == "https://fake.varbi.com/jobs/1"
    assert (kista.latitude, kista.longitude) == (57.71, 11.97)
    # Swedish local time, stored as UTC.
    assert abs((kista.posted_at - (NOW - timedelta(hours=1))).total_seconds()) < 2


def test_goes_past_the_apis_page_limit_with_published_before():
    requests = []

    def handler(request):
        requests.append(request)
        offset = int(request.url.params["offset"])
        before = request.url.params.get("published-before")
        if before is None:
            # A busy window: 21 full pages, the last one ending two hours ago.
            hours = 2 if offset == 2000 else 1
            return httpx.Response(200, json={"hits": [
                ad(f"a{offset}-{i}", "Nurse", hours_ago=hours) for i in range(100)]})
        assert offset == 0
        return httpx.Response(200, json={"hits": [ad("older", "Hardware Engineer", hours_ago=3)]})

    jobs = list(jobtech.JobTechSource().search(query([term("Hardware Engineer")]),
                                               context(handler)))
    assert [job.source_job_id for job in jobs] == ["older"]
    assert len(requests) == 22
    assert requests[-1].url.params["published-before"]


def test_a_named_swedish_place_keeps_jobs_there_and_nearby():
    def handler(request):
        return httpx.Response(200, json={"hits": [
            ad("1", "Hardware Engineer", city="Göteborg"),
            ad("2", "Hardware Engineer", city="Mölndal"),  # next to Gothenburg
            ad("3", "Hardware Engineer", city="Luleå"),
        ]})

    gothenburg = Place(name="Gothenburg", local_name="Göteborg", country="SE", kind="city",
                       radius_km=None)
    jobs = list(jobtech.JobTechSource().search(
        query([term("Hardware Engineer")], places=[gothenburg]), context(handler)))
    assert [job.source_job_id for job in jobs] == ["1", "2"]


def test_asked_to_slow_down_keeps_what_was_found():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "0"})

    ctx = context(handler)
    assert list(jobtech.JobTechSource().search(query([term("Hardware Engineer")]), ctx)) == []
    assert ctx.report.status == "partial" and "slow down" in ctx.report.message


@pytest.mark.parametrize(("employment", "duration", "hours", "expected"), [
    ("Vanlig anställning", "Tills vidare", "Heltid", ["full_time_permanent"]),
    ("Vanlig anställning", "6 månader eller längre", "Heltid", ["fixed_term"]),
    ("Vanlig anställning", None, "Heltid", []),  # unclear: never left out for its type
    ("Tillsvidareanställning (inkl. eventuell provanställning)", None, "Deltid",
     ["full_time_permanent", "part_time"]),
    ("Tidsbegränsad anställning", None, None, ["fixed_term"]),
    ("Behovsanställning", None, "Heltid", ["part_time"]),
    ("Sommarjobb / feriejobb", None, None, ["fixed_term"]),
])
def test_swedish_employment_types(employment, duration, hours, expected):
    item = ad("1", "Job", employment_type={"label": employment},
              duration={"label": duration} if duration else None,
              working_hours_type={"label": hours} if hours else None)
    assert jobtech.to_found_job(item).job_types == expected


def test_work_abroad_and_remote_work():
    abroad = ad("1", "Job", workplace_address={"city": "Oslo", "country": "Norge"})
    assert jobtech.to_found_job(abroad) is None
    remote = ad("2", "Job", workplace_model={"label": "Distansarbete"})
    assert jobtech.to_found_job(remote).work_mode == "remote"


def test_a_place_named_twice_is_written_once():
    item = ad("1", "Job", workplace_address={"city": "TÄBY", "municipality": "Täby",
                                             "region": "Stockholms län", "country": "Sverige"})
    assert jobtech.to_found_job(item).location_text == "Täby, Stockholms län"
