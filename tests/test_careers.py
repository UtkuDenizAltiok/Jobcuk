"""Company career systems and the employer directory, with made-up companies and answers."""

import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import all_sources, ashby, careers, greenhouse, lever, recruitee, workable
from jobcu.sources import workday as wd
from jobcu.sources.base import FoundJob, JobQuery, SourceContext, SourceError, SourceReport
from jobcu.sources.careers import Employer, job_types_from_text, keep_job
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)


def term(text, language="en", kind="job_title"):
    return SearchTerm(text=text, language=language, kind=kind)


def context(handler, source_id="test"):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport(source_id, source_id), lambda: False,
                         lambda message: None)


def employer(system="greenhouse", board="fakeco", countries=("IE", "GB"), elsewhere=True,
             name="FakeCo"):
    return Employer(name, system, board, tuple(countries), elsewhere)


def job(title="Hardware Engineer", location="Dublin, Ireland", country=None, hours_ago=2,
        description=""):
    return FoundJob(source="greenhouse", source_job_id="fakeco/1", url="https://example.test/1",
                    title=title, location_text=location, country=country,
                    posted_at=NOW - timedelta(hours=hours_ago), date_precision="exact",
                    description=description)


def query(countries=("IE",), terms=None, places=(), hours=24):
    return JobQuery(list(countries), list(places), terms or [term("Hardware Engineer")], hours, NOW)


# --- Keeping the right jobs -----------------------------------------------------------


def test_keeps_fresh_matching_jobs_in_the_countries_searched():
    q = query(["IE", "GB"])
    start = NOW - timedelta(hours=24)
    kept = keep_job(job(), employer(), q, start)
    assert kept.country == "IE" and kept.company == "FakeCo"
    assert kept.employer_url == "https://example.test/1"  # the employer's own ad
    assert keep_job(job(hours_ago=30), employer(), q, start) is None
    assert keep_job(job(location="Munich, Germany"), employer(), q, start) is None
    assert keep_job(job(location="Dublin, CA"), employer(), q, start) is None
    assert keep_job(job(title="Account Executive"), employer(), q, start) is None


def test_unclear_locations_depend_on_where_the_company_hires():
    q = query(["IE"])
    start = NOW - timedelta(hours=24)
    # A company that only hires in Ireland: an unclear place is taken as Ireland.
    only_ireland = employer(countries=("IE",), elsewhere=False)
    assert keep_job(job(location="Head Office"), only_ireland, q, start).country == "IE"
    # A company that also hires far away: only jobs open to Europe are kept.
    assert keep_job(job(location="Remote"), employer(), q, start) is None
    kept = keep_job(job(location="Remote - EMEA"), employer(countries=("IE", "GB")), q, start)
    assert kept is not None and kept.country == "IE"


def test_job_languages_and_places_follow_the_jobs_country():
    q = query(["DE"], terms=[term("Hardwareentwickler", "de")],
              places=[Place(name="Munich", local_name="München", country="DE", kind="city",
                            radius_km=None)])
    start = NOW - timedelta(hours=24)
    company = employer(countries=("DE",))
    assert keep_job(job("Hardwareentwickler (m/w/d)", "München, Germany"), company, q, start)
    assert keep_job(job("Hardwareentwickler (m/w/d)", "Berlin, Germany"), company, q, start) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Full-time", ["full_time_permanent", "fixed_term"]),
        ("Permanent", ["full_time_permanent"]),
        ("fulltime_permanent", ["full_time_permanent"]),
        ("fulltime_fixed_term", ["fixed_term"]),
        ("parttime_permanent", ["part_time"]),
        ("PartTime", ["part_time"]),
        ("Intern", ["internship_or_working_student"]),
        ("Werkstudent (Teilzeit)", ["internship_or_working_student", "part_time"]),
        ("Contract", ["freelance_or_contract", "fixed_term"]),
        ("Regular", ["full_time_permanent"]),
        ("", []),
        (None, []),
    ],
)
def test_job_types_from_career_system_wording(text, expected):
    assert job_types_from_text(text) == expected


# --- The common search ----------------------------------------------------------------


def test_one_company_failing_never_stops_the_others(monkeypatch):
    directory = (employer(board="gone"), employer(board="fakeco"), employer(board="other",
                                                                            countries=("DE",)))
    monkeypatch.setattr(careers, "load_directory", lambda: directory)

    def handler(request):
        if "/gone/" in request.url.path:
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(200, json={"jobs": [{
            "id": 7, "title": "Hardware Engineer", "location": {"name": "Cork, Ireland"},
            "first_published": NOW.isoformat(), "absolute_url": "https://example.test/7"}]})

    source = greenhouse.GreenhouseSource()
    ctx = context(handler, "greenhouse")
    assert source.covers(query(["IE"])) and not source.covers(query(["FR"]))
    jobs = list(source.search(query(["IE"]), ctx))
    assert [j.source_job_id for j in jobs] == ["fakeco/7"]
    assert ctx.report.requests == 2  # the German-only company wasn't read
    assert ctx.report.status == "partial" and "1 of 2" in ctx.report.message

    monkeypatch.setattr(careers, "load_directory", lambda: directory[:1])
    with pytest.raises(SourceError):
        list(source.search(query(["IE"]), context(handler, "greenhouse")))


def test_career_systems_are_part_of_every_search():
    ids = {source.id for source in all_sources()}
    assert {"greenhouse", "lever", "ashby", "workable", "recruitee", "workday"} <= ids


def test_the_shipped_directory_is_valid():
    entries = careers.load_directory()
    systems = {source.system for source in all_sources() if hasattr(source, "system")}
    for entry in entries:
        assert entry.system in systems
        assert entry.countries and set(entry.countries) <= set(careers.COUNTRIES)
    boards = [(e.system, e.board.lower()) for e in entries]
    assert len(boards) == len(set(boards))


# --- Greenhouse -----------------------------------------------------------------------


def test_greenhouse_lists_jobs_and_reads_the_full_ad():
    listing = {"jobs": [{"id": 11, "title": "Electronics Engineer",
                         "location": {"name": "Dublin, Ireland (Hybrid)"},
                         "first_published": "2026-09-16T09:30:00-04:00",
                         "updated_at": "2026-09-17T10:00:00-04:00",
                         "absolute_url": "https://job-boards.greenhouse.io/fakeco/jobs/11"}]}
    details = {"id": 11, "content": "&lt;p&gt;Design &amp;amp; test boards&lt;/p&gt;",
               "offices": [{"name": "Dublin", "location": "Dublin, Ireland"}]}

    def handler(request):
        assert request.url.host == "boards-api.greenhouse.io"
        if request.url.path == "/v1/boards/fakeco/jobs":
            return httpx.Response(200, json=listing)
        assert request.url.path == "/v1/boards/fakeco/jobs/11"
        return httpx.Response(200, json=details)

    source = greenhouse.GreenhouseSource()
    ctx = context(handler)
    found = list(source.list_jobs(employer(), ctx))[0]
    assert found.posted_at == datetime(2026, 9, 16, 13, 30, tzinfo=UTC)
    assert found.work_mode == "hybrid" and found.company == "FakeCo"
    full = source.load_details(found, ctx)
    assert full.description == "Design & test boards" and full.description_is_complete


# --- Lever ----------------------------------------------------------------------------


def test_lever_reads_country_full_ad_and_eu_servers():
    item = {"id": "abc", "text": "Power Electronics Engineer", "country": "DE",
            "categories": {"location": "Munich", "commitment": "Permanent"},
            "createdAt": int(datetime(2026, 9, 17, 8, 0, tzinfo=UTC).timestamp() * 1000),
            "descriptionPlain": "Build inverters.", "workplaceType": "on-site",
            "lists": [{"text": "Requirements", "content": "<li>EE degree</li>"}],
            "additionalPlain": "Equal opportunity.", "hostedUrl": "https://jobs.eu.lever.co/x/abc"}
    hosts = []

    def handler(request):
        hosts.append((request.url.host, request.url.path, request.url.params.get("mode")))
        return httpx.Response(200, json=[item])

    found = list(lever.LeverSource().list_jobs(employer("lever", "eu/fakeco"), context(handler)))
    assert hosts == [("api.eu.lever.co", "/v0/postings/fakeco", "json")]
    job_ = found[0]
    assert job_.country == "DE" and job_.work_mode == "on_site"
    assert job_.job_types == ["full_time_permanent"] and job_.description_is_complete
    assert "Build inverters." in job_.description and "• EE degree" in job_.description
    assert job_.posted_at == datetime(2026, 9, 17, 8, 0, tzinfo=UTC)


# --- Ashby, Workable, Recruitee -------------------------------------------------------


def test_ashby_joins_places_and_countries():
    item = {"id": "a1", "title": "Hardware Engineer", "location": "Office",
            "address": {"postalAddress": {"addressCountry": "Ireland"}},
            "secondaryLocations": [{
                "location": "London",
                "address": {"postalAddress": {"addressCountry": "United Kingdom"}}}],
            "publishedAt": "2026-09-17T08:00:00.000+00:00", "employmentType": "FullTime",
            "workplaceType": "Hybrid", "jobUrl": "https://jobs.ashbyhq.com/fakeco/a1",
            "descriptionPlain": "Boards and more."}
    found = ashby.to_found_job(item, employer("ashby"))
    assert found.location_text == "Office, Ireland; London, United Kingdom"
    assert found.work_mode == "hybrid" and found.description_is_complete
    assert found.job_types == ["full_time_permanent", "fixed_term"]


def test_workable_gives_days_and_reads_the_full_ad():
    listing = {"jobs": [{"title": "Test Engineer", "shortcode": "AB12",
                         "published_on": "2026-09-16",
                         "employment_type": "Full-time", "telecommuting": False,
                         "url": "https://apply.workable.com/j/AB12",
                         "locations": [{"city": "Galway", "country": "Ireland",
                                        "countryCode": "IE"}]}]}

    def handler(request):
        if request.url.path == "/api/v1/widget/accounts/fakeco":
            return httpx.Response(200, json=listing)
        assert request.url.path == "/api/v2/accounts/fakeco/jobs/AB12"
        return httpx.Response(200, json={"description": "<p>Test boards</p>",
                                         "requirements": "<ul><li>EE</li></ul>"})

    source = workable.WorkableSource()
    ctx = context(handler)
    found = list(source.list_jobs(employer("workable"), ctx))[0]
    assert found.country == "IE" and found.date_precision == "day"
    assert found.posted_at.date() == date(2026, 9, 16)
    assert source.load_details(found, ctx).description == "Test boards\n\n• EE"


def test_recruitee_reads_places_types_and_dates():
    item = {"id": 5, "title": "Firmware Engineer", "status": "published",
            "published_at": "2026-09-15 08:11:57 UTC", "employment_type_code": "fulltime_permanent",
            "hybrid": True, "careers_url": "https://fakeco.recruitee.com/o/firmware",
            "description": "<p>Firmware</p>", "requirements": "<p>C</p>",
            "locations": [{"city": "Amsterdam", "country": "Netherlands", "country_code": "NL"}]}
    found = recruitee.to_found_job(item, employer("recruitee"))
    assert found.country == "NL" and found.work_mode == "hybrid"
    assert found.posted_at == datetime(2026, 9, 15, 8, 11, 57, tzinfo=UTC)
    assert found.description == "Firmware\n\nC" and found.job_types == ["full_time_permanent"]


# --- Workday --------------------------------------------------------------------------


def test_workday_addresses_and_relative_dates():
    site = wd.parse_board("https://fakeco.wd3.myworkdayjobs.com/en-US/FakeCo_Careers")
    assert (site.host, site.tenant, site.site) == ("fakeco.wd3.myworkdayjobs.com", "fakeco",
                                                   "FakeCo_Careers")
    assert site.api == "https://fakeco.wd3.myworkdayjobs.com/wday/cxs/fakeco/FakeCo_Careers"
    today = date(2026, 9, 17)
    assert wd.posted_day("Posted Today", today) == today
    assert wd.posted_day("Posted Yesterday", today) == date(2026, 9, 16)
    assert wd.posted_day("Posted 3 Days Ago", today) == date(2026, 9, 14)
    assert wd.posted_day("Posted 30+ Days Ago", today) == date(2026, 8, 18)
    assert wd.posted_day("", today) is None


def workday_handler(pages, robots="User-agent: *\nAllow: /External/\n", seen=None):
    facets = [{"facetParameter": "locationMainGroup", "values": [
        {"facetParameter": "locationCountry", "values": [
            {"descriptor": "Ireland", "id": "ie-id", "count": 30},
            {"descriptor": "United States of America", "id": "us-id", "count": 70}]}]}]

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        if request.method == "GET":
            return httpx.Response(200, json={"jobPostingInfo": {
                "jobDescription": "<p>Design analog circuits</p>", "startDate": "2026-09-15",
                "timeType": "Full time", "remoteType": "Hybrid"}})
        body = json.loads(request.content)
        if seen is not None:
            seen.append(body)
        if not body["appliedFacets"]:
            return httpx.Response(200, json={"total": 100, "facets": facets, "jobPostings": []})
        page = body["offset"] // wd.PAGE_SIZE
        return httpx.Response(200, json={"total": 30, "jobPostings": pages[page]
                                         if page < len(pages) else []})

    return handler


def posting(title, posted, path):
    return {"title": title, "externalPath": path, "locationsText": "Ireland, Limerick",
            "postedOn": posted}


def test_workday_reads_the_searched_countries_newest_first_and_stops_at_old_jobs():
    fresh = [posting("Analog Design Engineer", "Posted Today", f"/job/Limerick/A_{i}")
             for i in range(20)]
    old = [posting("Analog Design Engineer", "Posted 30+ Days Ago", f"/job/Limerick/B_{i}")
           for i in range(20)]
    seen = []
    source = wd.WorkdaySource()
    ctx = context(workday_handler([fresh, old, old], seen=seen))
    board = employer("workday", "https://fakeco.wd1.myworkdayjobs.com/External")
    start = NOW - timedelta(hours=24)
    jobs = list(source.list_jobs(board, ctx, countries=["IE", "GB"], start=start))
    assert [body["appliedFacets"] for body in seen] == [{}, {"locationCountry": ["ie-id"]},
                                                         {"locationCountry": ["ie-id"]}]
    assert len(jobs) == 40 and jobs[0].country == "IE"
    assert jobs[0].url == "https://fakeco.wd1.myworkdayjobs.com/External/job/Limerick/A_0"

    full = source.load_details(jobs[0], ctx)
    assert full.description == "Design analog circuits"
    assert full.posted_at.date() == date(2026, 9, 15)
    assert full.work_mode == "hybrid" and full.job_types == ["full_time_permanent", "fixed_term"]

    counts = wd.WorkdaySource().country_counts(board, context(workday_handler([])))
    assert counts == {"IE": 30, "other": 70}


def test_workday_respects_robots_txt():
    source = wd.WorkdaySource()
    ctx = context(workday_handler([], robots="User-agent: *\nDisallow: /wday/\n"))
    board = employer("workday", "https://fakeco.wd1.myworkdayjobs.com/External")
    with pytest.raises(SourceError):
        list(source.list_jobs(board, ctx, countries=["IE"]))


def test_workday_finds_the_country_filter_whatever_it_is_called():
    # Some sites have a plain country filter, some a "Locations" list of countries, and some
    # only sites like "Ireland, Limerick". Places that name no country are ignored.
    facets = [{"facetParameter": "locationMainGroup", "values": [
        {"facetParameter": "locationHierarchy2", "values": [
            {"descriptor": "Office", "id": "office", "count": 10},
            {"descriptor": "Remote", "id": "remote", "count": 5}]},
        {"facetParameter": "locationHierarchy1", "values": [
            {"descriptor": "Ireland", "id": "ie", "count": 8},
            {"descriptor": "United States of America", "id": "us", "count": 40}]},
        {"facetParameter": "locations", "values": [
            {"descriptor": "Ireland, Limerick", "id": "ie-lim", "count": 5},
            {"descriptor": "Ireland, Cork", "id": "ie-cork", "count": 3},
            {"descriptor": "United States of America, Austin", "id": "us-aus", "count": 40}]}]}]
    parameter, values = wd._country_facet(facets)
    assert parameter == "locationHierarchy1"
    assert wd.country_facets({"facets": facets}) == {"ie": {"IE"}, "us": set()}
    assert len(values) == 2

    only_sites = [{"facetParameter": "locations", "values": [
        {"descriptor": "Germany, Munich", "id": "de-muc", "count": 2},
        {"descriptor": "Germany, Berlin", "id": "de-ber", "count": 1}]}]
    assert wd._country_facet(only_sites)[0] == "locations"
    assert wd.country_facets({"facets": only_sites}) == {"de-muc": {"DE"}, "de-ber": {"DE"}}
    assert wd._country_facet([{"facetParameter": "timeType", "values": [
        {"descriptor": "Full time", "id": "ft", "count": 3}]}]) == ("", [])
