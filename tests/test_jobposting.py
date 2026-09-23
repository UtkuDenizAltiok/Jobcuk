import json
from datetime import UTC, datetime

import httpx

from jobcu.jobposting import find_job_posting
from jobcu.keystore import KeyStore
from jobcu.sources.adzuna import AdzunaSource, details_page
from jobcu.sources.base import FoundJob, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient


def page(posting: dict, wrap_in_graph=False) -> str:
    data = {"@context": "https://schema.org", "@graph": [{"@type": "WebPage"}, posting]} \
        if wrap_in_graph else posting
    return f'<html><script type="application/ld+json">{json.dumps(data)}</script></html>'


POSTING = {
    "@type": "JobPosting",
    "title": "Power Electronics Engineer",
    "description": "<p>You design <b>inverters</b>.</p><ul><li>PCB layout</li></ul>" * 10,
    "datePosted": "2026-09-16T08:30:00+02:00",
    "employmentType": ["FULL_TIME", "INTERN"],
    "hiringOrganization": {"@type": "Organization", "name": "Acme GmbH"},
    "jobLocation": [{"@type": "Place", "address": {"addressLocality": "München"}}],
    "jobLocationType": "TELECOMMUTE",
}


def test_job_posting_data_is_read_even_inside_a_graph():
    posting = find_job_posting(page(POSTING, wrap_in_graph=True))
    assert posting.title == "Power Electronics Engineer"
    assert "• PCB layout" in posting.description and "<b>" not in posting.description
    assert posting.date_posted == datetime(2026, 9, 16, 6, 30, tzinfo=UTC)
    assert posting.company == "Acme GmbH" and posting.location_text == "München"
    assert posting.job_types == ["full_time_permanent", "fixed_term",
                                 "internship_or_working_student"]
    assert posting.remote


def test_pages_without_job_data_give_nothing():
    assert find_job_posting("<html><script type='application/ld+json'>{bad json</script>") is None
    assert find_job_posting(page({"@type": "Organization"})) is None


def adzuna_job():
    return FoundJob(source="adzuna", source_job_id="1", url="https://www.adzuna.de/land/ad/1",
                    title="Power Electronics Engineer", company="Acme GmbH",
                    description="Short start of the ad")


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("adzuna", "Adzuna"), lambda: False,
                         lambda message: None)


def test_adzuna_full_ad_is_read_from_the_details_page_even_for_landing_links():
    # Ads without a town link to /land/ad/<id>, which always refuses Jobcu; the same ad's
    # /details/<id> page carries the full text (checked live, 2026-09-23).
    asked = []

    def handler(request):
        asked.append(request.url.path)
        if request.url.path.startswith("/land/"):
            return httpx.Response(403, text="Zugriff verweigert")
        return httpx.Response(200, text=page(POSTING))

    source = AdzunaSource()
    ctx = context(handler)
    for _ in range(4):
        full = source.load_details(adzuna_job(), ctx)
    assert full.description_is_complete and "inverters" in full.description
    assert full.url == "https://www.adzuna.de/land/ad/1"  # the person's link stays as it was
    assert full.employer_url is None and full.work_mode == "remote"
    assert set(asked) == {"/details/1"} and not source.pages_refused


def test_adzuna_details_page_leading_to_the_employer_makes_that_the_main_link():
    def handler(request):
        if request.url.host == "www.adzuna.de":
            return httpx.Response(302, headers={"location": "https://careers.acme.example/42"})
        return httpx.Response(200, text=page(POSTING))

    job = FoundJob(**{**adzuna_job().__dict__, "url": "https://www.adzuna.de/details/42?x=1"})
    full = AdzunaSource().load_details(job, context(handler))
    assert full.description_is_complete
    assert full.employer_url == "https://careers.acme.example/42"


def test_adzuna_details_page_address():
    assert details_page("https://www.adzuna.de/land/ad/5894110270?se=a&v=B") == (
        "https://www.adzuna.de/details/5894110270")
    assert details_page("https://www.adzuna.co.uk/land/ad/12/") == (
        "https://www.adzuna.co.uk/details/12")
    for unchanged in ("https://www.adzuna.de/details/5?utm_medium=api",
                      "https://example.com/land/ad/5", "https://www.adzuna.de/land/ad/x"):
        assert details_page(unchanged) == unchanged


def test_one_refused_page_is_skipped_but_others_are_still_read():
    def handler(request):
        if request.url.path.endswith("/refused"):
            return httpx.Response(403, text="Zugriff verweigert")
        return httpx.Response(200, text=page(POSTING))

    source = AdzunaSource()
    ctx = context(handler)
    refused = source.load_details(
        FoundJob(**{**adzuna_job().__dict__, "url": "https://www.adzuna.de/land/ad/refused"}), ctx
    )
    assert not refused.description_is_complete and not source.pages_refused
    assert source.load_details(adzuna_job(), ctx).description_is_complete


def test_adzuna_pages_stop_after_repeated_refusals_or_a_robot_check():
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(403, text="Forbidden")

    source = AdzunaSource()
    ctx = context(handler)
    for _ in range(5):
        source.load_details(adzuna_job(), ctx)
    assert len(calls) == 3 and source.pages_refused

    robot = AdzunaSource()
    robot_ctx = context(lambda request: httpx.Response(403, text="Please solve the CAPTCHA"))
    robot.load_details(adzuna_job(), robot_ctx)
    assert robot.pages_refused
