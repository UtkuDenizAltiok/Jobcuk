"""NAV's job ad feed (Norway), with made-up answers (never the real site)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import nav
from jobcu.sources.base import JobQuery, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)
OSLO = ZoneInfo("Europe/Oslo")
TOKEN = "aaa.bbb.ccc"


def term(text, language="no", kind="job_title"):
    return SearchTerm(text=text, language=language, kind=kind)


def feed_item(uuid, title, status="ACTIVE"):
    return {"id": uuid, "url": f"/api/v1/feedentry/{uuid}", "title": title,
            "_feed_entry": {"uuid": uuid, "status": status, "title": title,
                            "businessName": "Eksempel AS", "municipal": "OSLO"}}


def full_entry(uuid, title, days_ago=0, city="OSLO", country="NORGE", engagement="Fast",
               extent="Heltid"):
    published = (NOW.astimezone(OSLO) - timedelta(days=days_ago)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return {"uuid": uuid, "status": "ACTIVE", "ad_content": {
        "uuid": uuid, "title": title, "jobtitle": "Sykepleier",
        "published": published.isoformat(), "applicationDue": "2026-10-18T00:00:00",
        "workLocations": [{"country": country, "city": city, "municipal": city,
                           "county": "OSLO", "postalCode": "0150"}],
        "employer": {"name": "Eksempel Sykehus"}, "engagementtype": engagement,
        "extent": extent, "applicationUrl": f"https://eksempel.reachmee.example/{uuid}",
        "link": f"https://arbeidsplassen.nav.no/stillinger/stilling/{uuid}",
        "contactList": [{"name": "Kari Nordmann", "phone": "12345678"}],
        "description": "<p>Vi søker sykepleier til intensivavdelingen.</p>"}}


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("nav", "NAV"),
                         lambda: False, lambda message: None)


def query(terms, hours=24, places=()):
    return JobQuery(countries=["NO"], places=list(places), terms=terms,
                    posted_within_hours=hours, started_at=NOW)


def test_reads_the_changed_entries_and_the_full_ads_of_matching_titles():
    asked = []
    entries = {
        "a": full_entry("a", "Sykepleier intensiv"),
        "c": full_entry("c", "Sykepleier", days_ago=40),  # an old ad that changed today
        "d": full_entry("d", "Sykepleier", country="SVERIGE", city="STOCKHOLM"),
    }

    def handler(request):
        asked.append(request.url.path)
        if request.url.path == "/api/publicToken":
            text = f"Current public token for Nav Job Vacancy Feed:\n{TOKEN}\n"
            return httpx.Response(200, text=text)
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        if request.url.path == "/api/v1/feed":
            assert "GMT" in request.headers["If-Modified-Since"]
            return httpx.Response(200, json={"items": [
                feed_item("a", "Sykepleier intensiv"), feed_item("b", "Butikksjef"),
                feed_item("c", "Sykepleier"), feed_item("d", "Sykepleier"),
                feed_item("e", "Sykepleier", status="INACTIVE"),
                feed_item("a", "Sykepleier intensiv")],  # changed again: read once
                "next_url": "/api/v1/feed/page2"})
        if request.url.path == "/api/v1/feed/page2":
            return httpx.Response(200, json={"items": [], "next_url": None})
        uuid = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=entries[uuid])

    jobs = list(nav.NavSource().search(query([term("Sykepleier")]), context(handler)))
    assert [job.source_job_id for job in jobs] == ["a"]
    # Only matching, active titles were opened: not "b" (another job) nor "e" (inactive).
    opened = [path.rsplit("/", 1)[-1] for path in asked if "/feedentry/" in path]
    assert opened == ["a", "c", "d"]
    job = jobs[0]
    assert job.company == "Eksempel Sykehus" and job.location_text == "Oslo"
    assert job.country == "NO" and job.date_precision == "day"
    assert job.employer_url == "https://eksempel.reachmee.example/a"
    assert job.job_types == ["full_time_permanent"]
    assert job.closes_at == datetime(2026, 10, 18, 21, 59, tzinfo=UTC)  # end of day in Oslo
    assert job.description_is_complete and "intensivavdelingen" in job.description
    assert "Kari Nordmann" not in job.description and "12345678" not in job.description


def test_engagement_types_and_hours():
    assert nav._job_types("Fast", "Heltid") == ["full_time_permanent"]
    assert nav._job_types("Fast", "Deltid") == ["part_time"]
    assert nav._job_types("Vikariat", "Heltid") == ["fixed_term"]
    assert nav._job_types("Lærling", "Heltid") == ["internship_or_working_student"]
    assert nav._job_types("Annet", "Heltid") == []


def test_named_places_are_matched():
    def handler(request):
        if request.url.path == "/api/publicToken":
            return httpx.Response(200, text=TOKEN)
        if request.url.path == "/api/v1/feed":
            return httpx.Response(200, json={"items": [feed_item("a", "Sykepleier"),
                                                       feed_item("b", "Sykepleier")],
                                             "next_url": None})
        uuid = request.url.path.rsplit("/", 1)[-1]
        city = "BERGEN" if uuid == "a" else "TROMSØ"
        return httpx.Response(200, json=full_entry(uuid, "Sykepleier", city=city))

    bergen = Place(name="Bergen", local_name="Bergen", country="NO", kind="city",
                   radius_km=None)
    jobs = list(nav.NavSource().search(query([term("Sykepleier")], places=[bergen]),
                                       context(handler)))
    assert [job.source_job_id for job in jobs] == ["a"]


def test_a_missing_token_fails_only_this_source():
    ctx = context(lambda request: httpx.Response(200, text="no token today"))
    try:
        list(nav.NavSource().search(query([term("Sykepleier")]), ctx))
    except nav.SourceError as exc:
        assert "token" in str(exc)
    else:
        raise AssertionError("a missing token should raise SourceError")
