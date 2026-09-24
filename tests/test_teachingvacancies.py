"""Teaching Vacancies' open API and job pages, with made-up answers (never the real site)."""

from datetime import UTC, datetime, timedelta

import httpx

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import teachingvacancies as tv
from jobcu.sources.base import FoundJob, JobQuery, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)
TODAY = NOW.date()


def term(text, kind="job_title"):
    return SearchTerm(text=text, language="en", kind=kind)


def job(slug, title, days_ago=0, town="Exampleton", types=("FULL_TIME",), school="Fake Primary"):
    return {
        "@context": "http://schema.org", "@type": "JobPosting", "title": title,
        "datePosted": (TODAY - timedelta(days=days_ago)).isoformat(),
        "description": "<p>We are looking for a caring class teacher.</p>",
        "employmentType": list(types), "industry": "Education",
        "jobLocation": {"@type": "Place", "address": {
            "@type": "PostalAddress", "addressLocality": town, "addressRegion": "North West",
            "postalCode": "EX1 2PL", "addressCountry": "GB"}},
        "url": f"https://teaching-vacancies.service.gov.uk/jobs/{slug}",
        "hiringOrganization": {"@type": "Organization", "name": school},
        "validThrough": "2026-10-16T23:59:00+01:00",
    }


def answer(jobs, total_pages=5):
    return {"data": jobs, "meta": {"totalPages": total_pages, "count": 500},
            "links": {"next": "…"}}


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("teachingvacancies", "Teaching Vacancies"),
                         lambda: False, lambda message: None)


def query(terms, hours=24, places=()):
    return JobQuery(countries=["GB"], places=list(places), terms=terms,
                    posted_within_hours=hours, started_at=NOW)


def test_reads_newest_pages_until_the_window_ends():
    pages = {
        1: [job("a", "Primary Class Teacher"), job("b", "Cleaner"),
            job("c", "Year 3 Teacher", types=("PART_TIME", "TEMPORARY"))],
        2: [job("d", "Primary Teacher", days_ago=1), job("e", "Class Teacher", days_ago=5)],
        3: [job("f", "Teacher", days_ago=9)],  # never asked for: page 2 already ended the window
    }
    asked = []

    def handler(request):
        page = int(request.url.params["page"])
        asked.append(page)
        return httpx.Response(200, json=answer(pages[page]))

    jobs = list(tv.TeachingVacanciesSource().search(query([term("Teacher")], hours=48),
                                                    context(handler)))
    assert asked == [1, 2]
    assert [j.source_job_id for j in jobs] == ["a", "c", "d"]
    first = jobs[0]
    assert first.company == "Fake Primary" and first.location_text == "Exampleton"
    assert first.country == "GB" and first.date_precision == "day"
    assert first.posted_at.date() == TODAY
    assert first.job_types == ["full_time_permanent"]
    assert jobs[1].job_types == ["fixed_term", "part_time"]  # "TEMPORARY" is a fixed term
    assert first.description == "We are looking for a caring class teacher."
    assert first.closes_at == datetime(2026, 10, 16, 22, 59, tzinfo=UTC)
    assert not first.description_is_complete  # the page has the rest


def test_stops_at_the_last_page():
    asked = []

    def handler(request):
        asked.append(request.url.params["page"])
        return httpx.Response(200, json=answer([job("a", "Teacher")], total_pages=1))

    assert len(list(tv.TeachingVacanciesSource().search(query([term("Teacher")]),
                                                         context(handler)))) == 1
    assert asked == ["1"]


def test_named_places_are_matched():
    def handler(request):
        return httpx.Response(200, json=answer(
            [job("a", "Teacher", town="Manchester"), job("b", "Teacher", town="Leeds")],
            total_pages=1))

    manchester = Place(name="Manchester", local_name="Manchester", country="GB", kind="city",
                       radius_km=None)
    jobs = list(tv.TeachingVacanciesSource().search(
        query([term("Teacher")], places=[manchester]), context(handler)))
    assert [j.location_text for j in jobs] == ["Manchester"]


def test_a_failing_api_fails_only_this_source():
    ctx = context(lambda request: httpx.Response(500, text="down"))
    try:
        list(tv.TeachingVacanciesSource().search(query([term("Teacher")]), ctx))
    except tv.SourceError as exc:
        assert "Teaching Vacancies" in str(exc)
    else:
        raise AssertionError("a failing API should raise SourceError")


def summary():
    return FoundJob(source="teachingvacancies", source_job_id="a",
                    url="https://teaching-vacancies.service.gov.uk/jobs/a", title="Teacher",
                    description="We are looking for a caring class teacher.")


PAGE = """<html><body><main><h1>Primary Class Teacher</h1>
<p>11 days remaining to apply</p>
<h2>Job details</h2><dl><dt>Visa sponsorship</dt><dd>Visas cannot be sponsored</dd>
<dt>Contract type</dt><dd>Permanent</dd><dt>Pay scale</dt><dd>Main Pay Scale</dd></dl>
<h2>What skills and experience we're looking for</h2>
<p>We are looking for a caring class teacher who can inspire children in Key Stage 2 and
work closely with families and colleagues across the school every day.</p>
<h2>What the school offers its staff</h2><p>A friendly team, training and a supportive
leadership, with time for planning and a clear path for career development.</p>
</main></body></html>"""


def test_the_job_page_gives_the_full_ad():
    ctx = context(lambda request: httpx.Response(200, text=PAGE))
    full = tv.TeachingVacanciesSource().load_details(summary(), ctx)
    assert full.description_is_complete
    assert "Visas cannot be sponsored" in full.description


def test_a_page_that_says_less_keeps_the_summary():
    job = summary()
    ctx = context(lambda request: httpx.Response(200, text="<html><body></body></html>"))
    assert tv.TeachingVacanciesSource().load_details(job, ctx) == job
    missing = context(lambda request: httpx.Response(404, text="gone"))
    assert tv.TeachingVacanciesSource().load_details(job, missing) == job
