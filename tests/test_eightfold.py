"""Eightfold career sites and the robots.txt reader, with made-up sites and answers."""

import json
from datetime import UTC, datetime, timedelta

import httpx

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.sources import all_sources, eightfold
from jobcu.sources.base import SourceContext, SourceReport
from jobcu.sources.careers import Employer
from jobcu.sources.http import PoliteClient, RobotsRules

NOW = datetime.now(UTC)
EMPLOYER = Employer("Example Semiconductors", "eightfold", "jobs.example.com/example.com",
                    ("DE",))
ROBOTS = """User-agent: *
Disallow: /
Allow: /$
Allow: /careers
Allow: /api/apply
"""


def term(text):
    return SearchTerm(text=text, language="en", kind="job_title")


def entry(job_id, slug, hours_ago=2):
    changed = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f"<url><loc>https://jobs.example.com/careers/job/{job_id}-{slug}?domain=example.com"
            f"</loc><priority>1.0</priority><lastmod>{changed}</lastmod></url>")


def sitemap(*entries):
    return ('<?xml version="1.0" encoding="UTF-8"?><urlset '
            f'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{"".join(entries)}</urlset>')


def page(title, town):
    data = {"@type": "JobPosting", "title": title, "datePosted": NOW.isoformat(),
            "validThrough": "2027-03-22T10:39:53Z", "employmentType": "FULL_TIME",
            "description": "<p>Design power stages for SiC inverters.</p>",
            "hiringOrganization": {"name": "Example"},
            "jobLocation": {"address": {"addressLocality": town}}}
    return f'<html><script type="application/ld+json">{json.dumps(data)}</script></html>'


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("eightfold", "Eightfold"),
                         lambda: False, lambda message: None)


def test_robots_rules_follow_the_standard_not_the_first_match():
    rules = RobotsRules(ROBOTS)
    assert rules.allows("https://jobs.example.com/careers/sitemap.xml?domain=example.com")
    assert rules.allows("https://jobs.example.com/")
    assert not rules.allows("https://jobs.example.com/admin")
    # The longest rule wins; an Allow wins a tie; "$" anchors; "*" matches anything.
    tie = RobotsRules("User-agent: *\nDisallow: /jobs\nAllow: /jobs")
    assert tie.allows("https://x.example/jobs/1")
    wild = RobotsRules("User-agent: *\nDisallow: /*?*feat=\nDisallow: /*.pdf$")
    assert not wild.allows("https://x.example/list?feat=1")
    assert not wild.allows("https://x.example/a.pdf") and wild.allows("https://x.example/a.pdf?x")
    # A group for Jobcu by name replaces the one for every robot.
    named = RobotsRules("User-agent: *\nDisallow: /\n\nUser-agent: Jobcu\nAllow: /")
    assert named.allows("https://x.example/anything")
    assert RobotsRules("User-agent: *\nDisallow:").allows("https://x.example/a")


def test_opens_only_recent_jobs_whose_address_matches():
    opened = []

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        if request.url.path == "/careers/sitemap.xml":
            assert request.url.params["domain"] == "example.com"
            return httpx.Response(200, text=sitemap(
                entry(1, "power-electronics-engineer-munich"),
                entry(2, "senior-accountant-munich"),  # not what was searched
                entry(3, "power-electronics-engineer-dresden", hours_ago=24 * 9)))  # old
        opened.append(request.url.path)
        return httpx.Response(200, text=page("Power Electronics Engineer (f/m/div)", "Munich"))

    jobs = list(eightfold.EightfoldSource().list_jobs(
        EMPLOYER, context(handler), countries=["DE"], start=NOW - timedelta(hours=24),
        terms=[term("Power Electronics Engineer")]))
    assert opened == ["/careers/job/1-power-electronics-engineer-munich"]
    job = jobs[0]
    assert job.title == "Power Electronics Engineer (f/m/div)" and job.location_text == "Munich"
    assert job.source_job_id == "jobs.example.com/1" and job.company == "Example Semiconductors"
    assert job.date_precision == "exact" and job.description_is_complete
    assert job.closes_at == datetime(2027, 3, 22, 10, 39, 53, tzinfo=UTC)


def test_the_directory_check_reads_places_from_the_addresses_alone():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        if request.url.path == "/careers/sitemap.xml":
            return httpx.Response(200, text=sitemap(entry(1, "test-engineer-dresden")))
        raise AssertionError("no job page is opened for the directory check")

    survey = eightfold.EightfoldSource().survey(EMPLOYER, context(handler))
    assert survey.counts["DE"] == 1


def test_a_site_whose_robots_txt_forbids_it_is_skipped():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /")
        raise AssertionError("nothing else may be asked")

    try:
        list(eightfold.EightfoldSource().list_jobs(EMPLOYER, context(handler), start=NOW,
                                                   terms=[term("Engineer")]))
    except eightfold.SourceError as exc:
        assert "doesn't allow" in str(exc)
    else:
        raise AssertionError("a closed site must raise SourceError")


def test_it_is_a_career_system_with_employers_in_the_directory():
    assert any(isinstance(source, eightfold.EightfoldSource) for source in all_sources())
    assert len(eightfold.EightfoldSource().employers(["DE", "GB", "IE"])) >= 4
