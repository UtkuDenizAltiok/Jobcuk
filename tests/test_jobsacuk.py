"""jobs.ac.uk, with made-up pages shaped like the real ones."""

from datetime import UTC, date, datetime, timedelta

import httpx

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import jobsacuk
from jobcu.sources.base import JobQuery, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)
TODAY = NOW.date()


def result(advert_id, title, placed, location="Cambridge", employer="Fake University",
           salary="£40,000 to £50,000"):
    return f"""
    <div class="j-search-result__result" data-advert-id="{advert_id}">
      <div class="j-search-result__text">
        <a href="/job/AB{advert_id}/{title.lower().replace(' ', '-')}"> {title} </a>
        <div class="j-search-result__department">Department of Physics</div>
        <div class="j-search-result__employer"><b>{employer}</b></div>
        <div>Location: {location}</div>
        <div class="j-search-result__info"><strong>Salary: </strong>{salary}
          Grade 7</div>
        <div><strong>Date Placed: </strong>{placed}</div>
      </div>
    </div>"""


def page(results):
    return f"<html><body><div id='job-listings'>{''.join(results)}</div></body></html>"


JOB_PAGE = """<html><head><script type="application/ld+json">
{"@type": "JobPosting", "title": "Electronics Design Engineer",
 "hiringOrganization": {"name": "Fake University"},
 "datePosted": "2026-09-16T09:00:00Z", "employmentType": "FULL_TIME",
 "description": "<p>Design boards for physics experiments.</p>"}
</script></head><body></body></html>"""


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("jobsacuk", "jobs.ac.uk"), lambda: False,
                         lambda message: None)


def test_dates_on_the_search_page():
    assert jobsacuk.placed_on("Date Placed: 27 Aug", date(2026, 9, 17)) == date(2026, 8, 27)
    # A day that hasn't come yet this year must be from last year.
    assert jobsacuk.placed_on("Date Placed: 30 Dec", date(2026, 1, 5)) == date(2025, 12, 30)
    assert jobsacuk.placed_on("Date Placed: soon", date(2026, 9, 17)) is None


def test_reads_the_newest_jobs_and_keeps_the_countries_searched():
    today = TODAY.strftime("%d %b")
    old = (TODAY - timedelta(days=9)).strftime("%d %b")
    asked = []

    def handler(request):
        asked.append(dict(request.url.params))
        if request.url.params.get("startIndex") != "1":
            return httpx.Response(200, text=page([]))
        return httpx.Response(200, text=page([
            result(1, "Electronics Design Engineer", today),
            result(2, "Lecturer in Physics", today, location="Dubai"),
            result(3, "Research Engineer", today, location="Dublin, Ireland"),
            result(4, "Electronics Engineer", old),
        ]))

    query = JobQuery(["GB", "IE"], [], [SearchTerm(text="Engineer", language="en",
                                                   kind="job_title")], 24, NOW)
    jobs = list(jobsacuk.JobsAcUkSource().search(query, context(handler)))
    assert [job.source_job_id for job in jobs] == ["1", "3", "4"]  # Dubai is left out
    assert asked[0]["sortOrder"] == "1" and asked[0]["keywords"] == "Engineer"
    assert jobs[0].url == "https://www.jobs.ac.uk/job/AB1/electronics-design-engineer"
    assert jobs[0].company == "Fake University" and jobs[0].country == "GB"
    assert jobs[0].salary_text == "£40,000 to £50,000 · Grade 7"
    assert jobs[1].source_job_id == "3" and jobs[1].country == "IE"


def test_named_places_are_matched():
    def handler(request):
        return httpx.Response(200, text=page([
            result(1, "Research Engineer", TODAY.strftime("%d %b"), location="Cambridge"),
            result(2, "Research Engineer", TODAY.strftime("%d %b"), location="Glasgow"),
        ]))

    cambridge = Place(name="Cambridge", local_name="Cambridge", country="GB", kind="city",
                      radius_km=None)
    query = JobQuery(["GB"], [cambridge], [SearchTerm(text="Engineer", language="en",
                                                      kind="job_title")], 24, NOW)
    jobs = list(jobsacuk.JobsAcUkSource().search(query, context(handler)))
    assert [job.source_job_id for job in jobs] == ["1"]


def test_the_full_ad_comes_from_the_jobs_own_page():
    job = jobsacuk.parse_results(page([result(1, "Electronics Design Engineer",
                                              TODAY.strftime("%d %b"))]), TODAY)[0]
    full = jobsacuk.JobsAcUkSource().load_details(
        job, context(lambda request: httpx.Response(200, text=JOB_PAGE)))
    assert full.description == "Design boards for physics experiments."
    assert full.description_is_complete and full.date_precision == "exact"
    assert full.job_types == ["full_time_permanent", "fixed_term"]

    unchanged = jobsacuk.JobsAcUkSource().load_details(
        job, context(lambda request: httpx.Response(404, text="gone")))
    assert unchanged is job
