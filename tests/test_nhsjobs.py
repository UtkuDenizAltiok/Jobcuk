"""NHS Jobs' XML feed and job pages, with made-up answers (never the real site)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import nhsjobs
from jobcu.sources.base import FoundJob, JobQuery, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)
UK = ZoneInfo("Europe/London")


def term(text, kind="job_title"):
    return SearchTerm(text=text, language="en", kind=kind)


def vacancy(ref, title, hours_ago=1, place="Exampleton, EX1 2PL", kind="Permanent",
            employer="Fake Hospitals NHS Foundation Trust"):
    posted = (NOW - timedelta(hours=hours_ago)).astimezone(UK).replace(tzinfo=None)
    return (f"<vacancyDetails><id>1</id><reference>{ref}</reference><title>{title}</title>"
            "<description>We are looking for a caring nurse to join our ward team...</description>"
            f"<employer>{employer}</employer><type>{kind}</type>"
            "<salary>£31049.00 to £37796.00</salary><closeDate>2026-10-08</closeDate>"
            f"<postDate>{posted.isoformat()}123</postDate>"
            f"<url>https://beta.jobs.nhs.uk/candidate/jobadvert/{ref}</url>"
            f"<locations><location>{place}</location></locations></vacancyDetails>")


def feed(*vacancies, pages=3):
    return (f"<?xml version='1.0' encoding='UTF-8'?><nhsJobs>{''.join(vacancies)}"
            f"<totalPages>{pages}</totalPages><totalResults>250</totalResults></nhsJobs>")


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("nhsjobs", "NHS Jobs"),
                         lambda: False, lambda message: None)


def query(terms, hours=24, places=()):
    return JobQuery(countries=["GB"], places=list(places), terms=terms,
                    posted_within_hours=hours, started_at=NOW)


def full_page(*vacancies):
    """A page of exactly 100 jobs, so reading goes on to the next page."""
    filler = [vacancy(f"F{n}", "Porter", hours_ago=2) for n in range(100 - len(vacancies))]
    return feed(*vacancies, *filler)


def test_reads_newest_pages_until_the_window_ends():
    pages = {
        1: full_page(vacancy("A1", "Staff Nurse"), vacancy("A2", "Ward Clerk"),
                     vacancy("A3", "Bank Staff Nurse", kind="Bank")),
        2: feed(vacancy("B1", "Staff Nurse - Critical Care", hours_ago=20),
                vacancy("B2", "Staff Nurse", hours_ago=30)),
        3: feed(vacancy("C1", "Staff Nurse", hours_ago=50)),
    }
    asked = []

    def handler(request):
        page = int(request.url.params["page"])
        asked.append(page)
        assert request.url.params["limit"] == "100"
        assert request.url.params["sort"] == "publicationDateDesc"
        return httpx.Response(200, text=pages[page])

    jobs = list(nhsjobs.NhsJobsSource().search(query([term("Staff Nurse")]), context(handler)))
    assert asked == [1, 2]
    assert [job.source_job_id for job in jobs] == ["A1", "A3", "B1"]
    first = jobs[0]
    assert first.url == "https://www.jobs.nhs.uk/candidate/jobadvert/A1"
    assert first.company == "Fake Hospitals NHS Foundation Trust"
    assert first.location_text == "Exampleton, EX1 2PL" and first.country == "GB"
    assert first.salary_text == "£31,049 to £37,796"
    assert first.closes_at == datetime(2026, 10, 8, 22, 59, tzinfo=UTC)  # the day's end, UK time
    assert first.date_precision == "exact"
    assert abs((first.posted_at - (NOW - timedelta(hours=1))).total_seconds()) < 2
    assert first.job_types == []  # "Permanent" doesn't say full or part time
    assert jobs[1].job_types == ["part_time"]  # bank staff are called in when needed
    assert not first.description_is_complete


def test_named_places_are_matched():
    def handler(request):
        return httpx.Response(200, text=feed(
            vacancy("A1", "Staff Nurse", place="Leeds, LS1 3EX"),
            vacancy("A2", "Staff Nurse", place="Bristol, BS2 8HW")))

    leeds = Place(name="Leeds", local_name="Leeds", country="GB", kind="city", radius_km=None)
    jobs = list(nhsjobs.NhsJobsSource().search(query([term("Staff Nurse")], places=[leeds]),
                                               context(handler)))
    assert [job.source_job_id for job in jobs] == ["A1"]


def test_a_failing_feed_fails_only_this_source():
    ctx = context(lambda request: httpx.Response(502, text="bad gateway"))
    try:
        list(nhsjobs.NhsJobsSource().search(query([term("Staff Nurse")]), ctx))
    except nhsjobs.SourceError as exc:
        assert "NHS Jobs" in str(exc)
    else:
        raise AssertionError("a failing feed should raise SourceError")


PAGE = """<html><body><nav>Menu</nav><main>
<h1>Staff Nurse</h1><h2>Job summary</h2><p>We are looking for a caring nurse to join our ward
team and help patients recover safely.</p>
<h3>Main duties of the job</h3><p>Assess, plan and give care to adult patients.</p>
<h2>Person Specification</h2><h3>Qualifications</h3><h4>Essential</h4>
<ul><li>Registered Nurse (Adult) with the NMC</li></ul>
<div class="show-mobile"><h3>Contract</h3><p id="contract_type">Permanent</p>
<h3 id="working_pattern_heading">Working pattern</h3><p> Full-time, Part-time </p></div>
<div class="hide-mobile"><h3>Working pattern</h3><p>Full-time, Part-time</p></div>
<form>Apply for this job</form></main></body></html>"""


def summary():
    return FoundJob(source="nhsjobs", source_job_id="A1",
                    url="https://www.jobs.nhs.uk/candidate/jobadvert/A1", title="Staff Nurse",
                    description="We are looking for a caring nurse to join our ward team...")


def test_the_job_page_gives_the_whole_ad():
    ctx = context(lambda request: httpx.Response(200, text=PAGE))
    full = nhsjobs.NhsJobsSource().load_details(summary(), ctx)
    assert full.description_is_complete
    assert "Registered Nurse (Adult) with the NMC" in full.description
    assert full.description.count("Working pattern") == 1  # the small-screen copy is dropped
    assert "Menu" not in full.description and "Apply for this job" not in full.description
    assert full.job_types == ["full_time_permanent", "part_time"]


def test_a_page_without_an_ad_keeps_the_summary():
    job = summary()
    empty = context(lambda request: httpx.Response(200, text="<html><body></body></html>"))
    assert nhsjobs.NhsJobsSource().load_details(job, empty) == job
    gone = context(lambda request: httpx.Response(404, text="gone"))
    assert nhsjobs.NhsJobsSource().load_details(job, gone) == job
