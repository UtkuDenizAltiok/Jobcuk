"""JobsIreland.ie, with made-up pages shaped like the real ones (never the real site)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import jobsireland
from jobcu.sources.base import JobQuery, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)
IRISH = ZoneInfo("Europe/Dublin")


def term(text, kind="job_title"):
    return SearchTerm(text=text, language="en", kind=kind)


def job_block(job_id, title, posted, *, company="Fake Devices Ltd", location="Swords, Co. Dublin",
              vacancy_type="0", closes="2026-11-05T00:00:00"):
    logo = f'<img src="logo.png" alt="Logo of {company}">' if company else ""
    return f"""
    <div class="job-heading position-box" data-vacancyid = "{job_id}" tabindex="0" >
      <input type="hidden" id="JobId" value="{job_id}" />
      <input type="hidden" id="JobTitle" value="{title}" />
      <input type="hidden" id="Location" value="{location}, " />
      <input type="hidden" id="StartDate" value="{posted.astimezone(IRISH):%Y-%m-%dT%H:%M:%S}" />
      <input type="hidden" id="EndDate" value="{closes}" />
      <input type="hidden" id="VacancyTypeId" value="{vacancy_type}" />
      <div class="flex-item">{logo}</div>
    </div>"""


def list_page(blocks, map_items=""):
    template = """<div class="job-heading" data-vacancyid = "#JobId">
      <input type="hidden" id="JobId" value="#JobId" /></div>"""
    return f"""<html><body><div id="jobslist">{''.join(blocks)}{template}</div>
      <ul class="drop" id="longlats" style="display: none;">{map_items}</ul></body></html>"""


DETAIL_PAGE = """<html><body>
  <ul class="job-detail_list">
    <li><div class="icon-images"><img alt="Image for Employer"></div>
        <div>Fake Devices Ltd</div></li>
    <li><div class="icon-images"><img alt="Image Part Time"></div><div>Paid Position</div></li>
    <li><div class="icon-images"><img alt="Image Hours per week"></div>
        <div>39 hours per week</div></li>
    <li><div class="icon-images"><img alt="Image for Euro"></div>
        <div>52000.00 Euro Annually</div></li>
  </ul>
  <pre ng-bind-html="Description | linky" class="ng-binding">Design power electronics.
Requirements:
	Degree in electronic engineering</pre>
</body></html>"""


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("jobsireland", "JobsIreland.ie"),
                         lambda: False, lambda message: None)


def test_reads_the_newest_jobs_and_keeps_matching_titles_until_they_are_too_old():
    fresh = NOW - timedelta(hours=3)
    old = NOW - timedelta(days=3)
    requests = []

    def handler(request):
        requests.append(dict(request.url.params))
        page = int(request.url.params["page"])
        if page == 1:
            blocks = [job_block(1000 + i, "Care Assistant", fresh) for i in range(98)]
            blocks += [job_block(1, "Electronics Hardware Engineer", fresh),
                       job_block(2, "Hardware Engineer", fresh)]
            return httpx.Response(200, text=list_page(
                blocks, "<li>53.45;-6.22;Swords , Co. Dublin;Hardware Engineer;2;#JOB-2</li>"))
        blocks = [job_block(3, "Hardware Engineer II", fresh),
                  job_block(4, "Hardware Engineer", old)] + [
            job_block(2000 + i, "Hardware Engineer", old) for i in range(98)]
        return httpx.Response(200, text=list_page(blocks))

    query = JobQuery(["IE"], [], [term("Hardware Engineer")], 24, NOW)
    jobs = list(jobsireland.JobsIrelandSource().search(query, context(handler)))

    assert [job.source_job_id for job in jobs] == ["1", "2", "3"]
    assert len(requests) == 2  # stopped at the first job older than the window
    assert requests[0]["pageSize"] == "100" and requests[0]["keyWord"] == ""
    job = jobs[1]
    assert job.url == "https://jobsireland.ie/en-US/job-Details?id=2"
    assert job.company == "Fake Devices Ltd" and job.country == "IE"
    assert job.location_text == "Swords, Co. Dublin"
    assert (job.latitude, job.longitude) == (53.45, -6.22)
    assert job.date_precision == "exact"
    assert abs(job.posted_at - fresh) < timedelta(seconds=1)  # Irish time read correctly
    # The closing date comes as that day at midnight: open until the day's end (Irish time).
    assert job.closes_at == datetime(2026, 11, 5, 23, 59, tzinfo=UTC)


def test_named_places_are_matched_against_the_address():
    fresh = NOW - timedelta(hours=1)

    def handler(request):
        return httpx.Response(200, text=list_page([
            job_block(1, "Hardware Engineer", fresh, location="Swords, Co. Dublin"),
            job_block(2, "Hardware Engineer", fresh, location="Ballincollig, Co. Cork"),
        ]))

    cork = Place(name="Cork", local_name="Corcaigh", country="IE", kind="city", radius_km=None)
    query = JobQuery(["IE"], [cork], [term("Hardware Engineer")], 24, NOW)
    jobs = list(jobsireland.JobsIrelandSource().search(query, context(handler)))
    assert [job.source_job_id for job in jobs] == ["2"]


def test_vacancy_types_become_job_types():
    fresh = NOW - timedelta(hours=1)
    jobs = jobsireland.parse_list(list_page([
        job_block(1, "Caretaker - CE Scheme", fresh, vacancy_type="3", company=None),
        job_block(2, "Electrician Apprentice", fresh, vacancy_type="4"),
        job_block(3, "Engineer", fresh, vacancy_type="0"),
    ]))
    assert [job.job_types for job in jobs] == [
        ["part_time"], ["internship_or_working_student"], []]
    assert jobs[0].company is None


def test_full_ad_employer_hours_and_salary_come_from_the_job_page():
    job = jobsireland.parse_list(list_page([
        job_block(7, "Hardware Engineer", NOW, company=None)]))[0]

    def handler(request):
        assert request.url.path == "/en-US/job-Details"
        return httpx.Response(200, text=DETAIL_PAGE)

    full = jobsireland.JobsIrelandSource().load_details(job, context(handler))
    assert full.description_is_complete
    assert full.description.startswith("Design power electronics.")
    assert "Degree in electronic engineering" in full.description
    assert full.company == "Fake Devices Ltd"
    assert full.job_types == ["full_time_permanent", "fixed_term"]
    assert full.salary_text == "€52,000 a year"


def test_part_time_hours_and_a_missing_page_are_handled():
    job = jobsireland.parse_list(list_page([job_block(8, "Technician", NOW)]))[0]
    part_time = DETAIL_PAGE.replace("39 hours per week", "20 hours per week").replace(
        "52000.00 Euro Annually", "13.50 - 15.00 Euro Hourly")
    details = jobsireland.apply_details(job, part_time)
    assert details.job_types == ["part_time"]
    assert details.salary_text == "€13.50 – €15 an hour"

    ctx = context(lambda request: httpx.Response(404, text="Not found"))
    assert jobsireland.JobsIrelandSource().load_details(job, ctx) is job


def test_a_changed_site_fails_only_this_source():
    ctx = context(lambda request: httpx.Response(500, text="Server error"))
    query = JobQuery(["IE"], [], [term("Hardware Engineer")], 24, NOW)
    try:
        list(jobsireland.JobsIrelandSource().search(query, ctx))
    except jobsireland.SourceError as exc:
        assert "JobsIreland.ie" in str(exc)
    else:
        raise AssertionError("expected a SourceError")


def test_an_empty_list_for_the_whole_country_is_reported_as_a_site_problem():
    # 2026-09-24 night: the site answered "No jobs match this search" to everything, and the
    # search showed JobsIreland.ie as fine with 0 jobs.
    ctx = context(lambda request: httpx.Response(200, text=list_page([])))
    query = JobQuery(["IE"], [], [term("Hardware Engineer")], 24, NOW)
    with pytest.raises(jobsireland.SourceError, match="listed no jobs at all"):
        list(jobsireland.JobsIrelandSource().search(query, ctx))
