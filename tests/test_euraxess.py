"""EURAXESS, with made-up pages shaped like the real ones."""

from datetime import UTC, datetime, timedelta

import httpx

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.sources import euraxess
from jobcu.sources.base import JobQuery, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)


def result(job_id, title, posted, country="Ireland", organisation="Fake University",
           location="Dublin"):
    return f"""
    <li><div id="job-teaser-content">
      <ul class="ecl-content-block__label-container">
        <li class="ecl-content-block__label-item">
          <span class="ecl-label ecl-label--low">JOB</span></li>
        <li class="ecl-content-block__label-item">
          <span class="ecl-label ecl-label--highlight">{country}</span></li>
      </ul>
      <article class="ecl-content-item"><div class="ecl-content-block">
        <ul class="ecl-content-block__primary-meta-container">
          <li class="ecl-content-block__primary-meta-item"><a href="/x">{organisation}</a></li>
          <li class="ecl-content-block__primary-meta-item">Posted on: {posted}</li>
        </ul>
        <h3 class="ecl-content-block__title"><a href="/jobs/{job_id}"><span>{title}</span></a></h3>
        <div class="ecl-content-block__description"><p>A short summary of the job.</p></div>
        <div class="id-Work-Locations">Work Locations: Number of offers: 1,
          {country}, {location}</div>
      </div></article>
    </div></li>"""


def page(results):
    return f"<html><body><ul>{''.join(results)}</ul></body></html>"


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("euraxess", "EURAXESS"), lambda: False,
                         lambda message: None)


def test_reads_the_newest_research_jobs_in_the_countries_searched():
    today = NOW.strftime("%d %B %Y")
    old = (NOW - timedelta(days=8)).strftime("%d %B %Y")
    asked = []

    def handler(request):
        asked.append(dict(request.url.params))
        return httpx.Response(200, text=page([
            result(1, "Postdoc in Power Electronics", today),
            result(2, "PhD in Photonics", today, country="Spain", location="Madrid"),
            result(3, "Research Engineer", old),
        ]))

    query = JobQuery(["IE"], [], [SearchTerm(text="electronics", language="en",
                                             kind="field_or_skill")], 24, NOW)
    jobs = list(euraxess.EuraxessSource().search(query, context(handler)))
    assert [job.source_job_id for job in jobs] == ["1"]  # Spain not searched, one too old
    assert asked[0]["sort[name]"] == "created" and asked[0]["sort[direction]"] == "DESC"
    assert len(asked) == 1  # a page with nothing fresh stops the paging
    job = jobs[0]
    assert job.url == "https://euraxess.ec.europa.eu/jobs/1"
    assert job.company == "Fake University" and job.country == "IE"
    assert job.location_text == "Ireland, Dublin"
    assert job.description == "A short summary of the job."


def test_the_full_ad_comes_from_the_jobs_own_page():
    job = euraxess.parse_results(page([result(1, "Postdoc", NOW.strftime("%d %B %Y"))]))[0]
    ad = ("<html><body><article><h1>Postdoc</h1>"
          "<p>Type of Contract: Temporary</p><p>Job Status: Full-time</p>"
          "<p>" + "We are looking for a postdoc in power electronics. " * 20 + "</p>"
          "</article></body></html>")
    full = euraxess.EuraxessSource().load_details(
        job, context(lambda request: httpx.Response(200, text=ad)))
    assert full.description_is_complete
    assert "power electronics" in full.description
    assert full.job_types == ["fixed_term"]

    unchanged = euraxess.EuraxessSource().load_details(
        job, context(lambda request: httpx.Response(500, text="oops")))
    assert unchanged is job
