"""Werken voor Nederland's sitemap and job pages, with made-up answers (never the real site)."""

import json
from datetime import UTC, datetime, timedelta

import httpx

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import werkenvoornederland as wvn
from jobcu.sources.base import JobQuery, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)
TODAY = NOW.date()


def term(text, language="nl", kind="job_title"):
    return SearchTerm(text=text, language=language, kind=kind)


def entry(slug, hours_ago=2):
    changed = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f"<url><changefreq>daily</changefreq><loc>{wvn.SITE}/vacatures/{slug}</loc>"
            f"<priority>0.7</priority><lastmod>{changed}</lastmod></url>")


def sitemap(*entries):
    return ('<?xml version="1.0" encoding="UTF-8"?><urlset '
            f'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{"".join(entries)}</urlset>')


def page(title, town="Utrecht", days_ago=0, kind="FULL_TIME"):
    data = {"@context": "https://schema.org/", "@type": "JobPosting", "title": title,
            "description": f"{title} in {town} voor 36 uur",
            "datePosted": (TODAY - timedelta(days=days_ago)).isoformat(),
            "validThrough": "2026-10-05", "employmentType": kind,
            "hiringOrganization": {"@type": "Organization", "name": " Ministerie van Voorbeeld"},
            "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress",
                                                          "addressLocality": town}}}
    ad = " ".join(["Je adviseert over wetgeving en werkt samen met collega's."] * 12)
    return (f'<html><head><script type="application/ld+json">{json.dumps(data)}</script>'
            f"</head><body><main><h1>{title}</h1><h2>Wat ga je doen</h2><p>{ad}</p>"
            "<h2>Wat vragen wij</h2><p>Een afgeronde master in de rechten en goede kennis van "
            "het bestuursrecht.</p></main></body></html>")


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("werkenvoornederland", "WvN"),
                         lambda: False, lambda message: None)


def query(terms, hours=24, places=()):
    return JobQuery(countries=["NL"], places=list(places), terms=terms,
                    posted_within_hours=hours, started_at=NOW)


def test_opens_only_the_recent_jobs_whose_address_matches():
    opened = []
    pages = {
        "juridisch-beleidsmedewerker-BZK-2026-1001": page("Juridisch beleidsmedewerker"),
        "juridisch-adviseur-JenV-2026-1002": page("Juridisch adviseur", days_ago=9),
    }

    def handler(request):
        if request.url.path.endswith("sitemap-vacatures.xml"):
            return httpx.Response(200, text=sitemap(
                entry("juridisch-beleidsmedewerker-BZK-2026-1001"),
                entry("juridisch-adviseur-JenV-2026-1002"),  # changed today, posted long ago
                entry("medewerker-ict-DJI-2026-1003"),  # not what was searched: never opened
                entry("juridisch-medewerker-CJIB-2026-1004", hours_ago=24 * 10),  # old change
            ))
        slug = request.url.path.rsplit("/", 1)[-1]
        opened.append(slug)
        return httpx.Response(200, text=pages[slug])

    terms = [term("Juridisch beleidsmedewerker"), term("Juridisch adviseur")]
    jobs = list(wvn.WerkenVoorNederlandSource().search(query(terms), context(handler)))
    assert opened == ["juridisch-beleidsmedewerker-BZK-2026-1001",
                      "juridisch-adviseur-JenV-2026-1002"]
    assert [job.source_job_id for job in jobs] == ["BZK-2026-1001"]
    job = jobs[0]
    assert job.title == "Juridisch beleidsmedewerker"
    assert job.company == "Ministerie van Voorbeeld" and job.location_text == "Utrecht"
    assert job.country == "NL" and job.date_precision == "day"
    assert job.description_is_complete and "bestuursrecht" in job.description
    assert job.closes_at == datetime(2026, 10, 5, 23, 59, tzinfo=UTC)
    assert job.job_types == ["full_time_permanent", "fixed_term"]


def test_named_places_are_matched():
    def handler(request):
        if request.url.path.endswith("sitemap-vacatures.xml"):
            return httpx.Response(200, text=sitemap(entry("beleidsmedewerker-IM-2026-1"),
                                                    entry("beleidsmedewerker-EZ-2026-2")))
        town = "Den Haag (Rijnstraat)" if request.url.path.endswith("-1") else "Groningen"
        return httpx.Response(200, text=page("Beleidsmedewerker", town=town))

    the_hague = Place(name="The Hague", local_name="Den Haag", country="NL", kind="city",
                      radius_km=None)
    jobs = list(wvn.WerkenVoorNederlandSource().search(
        query([term("Beleidsmedewerker")], places=[the_hague]), context(handler)))
    assert [job.source_job_id for job in jobs] == ["IM-2026-1"]


def test_a_failing_sitemap_fails_only_this_source():
    ctx = context(lambda request: httpx.Response(500, text="down"))
    try:
        list(wvn.WerkenVoorNederlandSource().search(query([term("Beleidsmedewerker")]), ctx))
    except wvn.SourceError as exc:
        assert "Werken voor Nederland" in str(exc)
    else:
        raise AssertionError("a failing sitemap should raise SourceError")
