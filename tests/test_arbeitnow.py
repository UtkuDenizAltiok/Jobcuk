"""Arbeitnow, with made-up answers (never the real site)."""

from datetime import UTC, datetime, timedelta

import httpx

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import arbeitnow
from jobcu.sources.base import JobQuery, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)


def term(text, language="en", kind="job_title"):
    return SearchTerm(text=text, language=language, kind=kind)


def item(slug, title, location, hours_ago=1, description="Design boards", remote=False):
    return {"slug": slug, "title": title, "location": location, "company_name": "FakeCo",
            "created_at": int((NOW - timedelta(hours=hours_ago)).timestamp()),
            "description": f"<p>{description}</p>", "job_types": ["Full Time"], "remote": remote,
            "url": f"https://www.arbeitnow.com/jobs/companies/fakeco/{slug}"}


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("arbeitnow", "Arbeitnow"), lambda: False,
                         lambda message: None)


def test_reads_pages_until_the_jobs_are_too_old_and_keeps_the_countries_searched():
    pages = {
        "1": [item("a", "Hardwareentwickler (m/w/d)", "München"),
              item("b", "Hardware Engineer", "London"),
              item("c", "Hardware Engineer", "Paris, France"),
              item("d", "Nurse", "Berlin")],
        "2": [item("e", "Hardware Engineer", "Hamburg", hours_ago=40)],
    }
    seen = []

    def handler(request):
        seen.append((request.url.host, request.url.params.get("page")))
        if request.url.host == "www.arbeitnow.co.uk":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json={"data": pages.get(request.url.params.get("page"), [])})

    query = JobQuery(["DE"], [], [term("Hardwareentwickler", "de"), term("Hardware Engineer")],
                     24, NOW)
    jobs = list(arbeitnow.ArbeitnowSource().search(query, context(handler)))
    assert [job.source_job_id for job in jobs] == ["a"]
    assert jobs[0].country == "DE" and jobs[0].description == "Design boards"
    assert jobs[0].job_types == ["full_time_permanent", "fixed_term"]
    assert seen == [("www.arbeitnow.com", "1"), ("www.arbeitnow.com", "2")]


def test_the_uk_list_is_only_read_when_the_uk_is_searched():
    seen = []

    def handler(request):
        seen.append(request.url.host)
        return httpx.Response(200, json={"data": [item("uk", "Hardware Engineer", "London")]})

    query = JobQuery(["GB"], [], [term("Hardware Engineer")], 24, NOW)
    jobs = list(arbeitnow.ArbeitnowSource().search(query, context(handler)))
    assert {job.country for job in jobs} == {"GB"}
    assert set(seen) == {"www.arbeitnow.com", "www.arbeitnow.co.uk"}


def test_named_places_and_unclear_locations():
    def handler(request):
        return httpx.Response(200, json={"data": [
            item("m", "Hardware Engineer", "Munich"),
            item("b", "Hardware Engineer", "Berlin"),
            item("x", "Hardware Engineer", "Remote"),
            item("e", "Hardware Engineer", "Remote - EMEA", remote=True),
        ]})

    munich = Place(name="Munich", local_name="München", country="DE", kind="city", radius_km=None)
    query = JobQuery(["DE"], [munich], [term("Hardware Engineer")], 24, NOW)
    jobs = list(arbeitnow.ArbeitnowSource().search(query, context(handler)))
    # "Remote - EMEA" has no country, so no place can rule it out; plain "Remote" is left out.
    assert [job.source_job_id for job in jobs] == ["m", "e"]
