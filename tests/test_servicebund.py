"""service.bund.de's job feed and job pages, with made-up answers (never the real site)."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from zoneinfo import ZoneInfo

import httpx

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import servicebund
from jobcu.sources.base import FoundJob, JobQuery, SourceContext, SourceReport
from jobcu.sources.http import SITE_INTERVALS, PoliteClient

NOW = datetime.now(UTC)
GERMANY = ZoneInfo("Europe/Berlin")


def term(text, language="de", kind="job_title"):
    return SearchTerm(text=text, language=language, kind=kind)


def item(job_id, title, employer="Stadt Beispielhausen", place="12345 Beispielhausen",
         hours_ago=2, midnight=False):
    when = (NOW - timedelta(hours=hours_ago)).astimezone(GERMANY)
    if midnight:
        when = when.replace(hour=0, minute=0, second=0, microsecond=0)
    link = (f"https://www.service.bund.de/IMPORTE/Stellenangebote/editor/Fake/2026/09/"
            f"{job_id}.html")
    return f"""<item>
<title>{title}</title>
<link>{link}#track=feed-jobs</link>
<description><![CDATA[
Arbeitgeber: <strong>{employer}</strong><br />
    Ort: <strong>{place}</strong>
 <br /><br />Bewerbungsfrist:  <strong>23.10.2026 23:59</strong> <br />
]]></description>
<pubDate>{format_datetime(when)}</pubDate>
<guid>{link}</guid>
</item>"""


def feed(*items):
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f"<title>Stellenangebote</title>{''.join(items)}</channel></rss>")


def page(hours="Vollzeit", duration="Befristet", pay="E 13 TVöD", text=True):
    ad = ("<!--Tätigkeit einfügen--><section><h2>Tätigkeitsprofil:</h2><ul><li>Beratung von "
          "Familien</li></ul><h2>Anforderungsprofil:</h2><ul><li>Studium der Sozialen Arbeit"
          "</li></ul></section><!--Tätigkeit ende-->") if text else ""
    return f"""<html><body><h1>Sozialarbeiter (m/w/d)</h1>
<section class="shortlist"><h1>Kurzinfo</h1><dl>
<dt>Tätigkeitsfeld</dt><dd>Soziales</dd>
<dt>Ort</dt><dd>Beispielhausen <br/><a href="#location-map" class="map">Karte anschauen</a></dd>
<dt>Arbeitszeit</dt><dd>{hours}</dd><dt>Anstellungsdauer</dt><dd>{duration}</dd>
<dt>Bewerbungsfrist</dt><dd>23.10.2026</dd><dt>Laufbahn / Entgeltgruppe</dt><dd>{pay}</dd>
</dl></section>{ad}
<a href="https://fake-bewerbung.example/job/1" target="_blank">Stellenangebot (HTML-Seite)
</a>
<div id="location-map" class="gsb-map-container" data-lat="52.5" data-lon="13.4"></div>
</body></html>"""


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("servicebund", "service.bund.de"),
                         lambda: False, lambda message: None)


def query(terms, hours=24, places=(), countries=("DE",)):
    return JobQuery(countries=list(countries), places=list(places), terms=terms,
                    posted_within_hours=hours, started_at=NOW)


def test_reads_the_feed_and_keeps_the_jobs_that_match():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=feed(
            item("1", "Sozialarbeiter (m/w/d)", employer="Universit&#228;t Beispiel"),
            item("2", "Sachbearbeitung Steuerwesen (m/w/d)"),  # not what was searched
            item("3", "Sozialarbeiterin im Jugendamt", hours_ago=30),  # older than the window
            item("4", "Sozialarbeiter (m/w/d)", place="Paris, Frankreich"),  # abroad, not searched
            item("5", "Sozialarbeiter (m/w/d) Kita", midnight=True),
        ))

    ctx = context(handler)
    jobs = list(servicebund.ServiceBundSource().search(query([term("Sozialarbeiter")]), ctx))
    assert [job.source_job_id for job in jobs] == ["1", "5"]
    assert len(requests) == 1 and ctx.report.requests == 1
    first = jobs[0]
    assert first.company == "Universität Beispiel"  # the feed's escaped umlauts
    assert first.location_text == "Beispielhausen" and first.country == "DE"
    assert first.url.endswith("/1.html")  # without "#track=feed-jobs"
    assert first.date_precision == "exact"
    assert abs((first.posted_at - (NOW - timedelta(hours=2))).total_seconds()) < 2
    assert "Bewerbungsfrist: 23.10.2026 23:59" in first.description
    assert first.closes_at == datetime(2026, 10, 23, 21, 59, tzinfo=UTC)  # German summer time
    assert not first.description_is_complete
    assert jobs[1].date_precision == "day"  # midnight means only the day is known


def test_named_places_are_matched():
    def handler(request):
        return httpx.Response(200, text=feed(
            item("1", "Sozialarbeiter", place="10115 Berlin"),
            item("2", "Sozialarbeiter", place="80331 München"),
        ))

    berlin = Place(name="Berlin", local_name="Berlin", country="DE", kind="city", radius_km=None)
    jobs = list(servicebund.ServiceBundSource().search(
        query([term("Sozialarbeiter")], places=[berlin]), context(handler)))
    assert [job.location_text for job in jobs] == ["Berlin"]


def test_says_when_the_feed_does_not_reach_back_far_enough():
    # 450 jobs from the last hour: the feed ends long before a week-long window starts.
    items = [item(str(n), "Sachbearbeitung", hours_ago=0.5) for n in range(450)]
    ctx = context(lambda request: httpx.Response(200, text=feed(*items)))
    list(servicebund.ServiceBundSource().search(query([term("Sozialarbeiter")], hours=168), ctx))
    assert ctx.report.status == "partial"
    assert "reaches back only to" in ctx.report.message


def test_a_broken_answer_fails_only_this_source():
    ctx = context(lambda request: httpx.Response(503, text="down"))
    try:
        list(servicebund.ServiceBundSource().search(query([term("Sozialarbeiter")]), ctx))
    except servicebund.SourceError as exc:
        assert "service.bund.de" in str(exc)
    else:
        raise AssertionError("a failing feed should raise SourceError")


def summary_job():
    return FoundJob(source="servicebund", source_job_id="1",
                    url="https://www.service.bund.de/IMPORTE/Stellenangebote/editor/Fake/1.html",
                    title="Sozialarbeiter (m/w/d)", company="Stadt Beispielhausen",
                    location_text="Beispielhausen", country="DE", description="Ort: …")


def test_the_job_page_gives_the_full_ad_and_its_facts():
    ctx = context(lambda request: httpx.Response(200, text=page()))
    full = servicebund.ServiceBundSource().load_details(summary_job(), ctx)
    assert full.description_is_complete
    assert "• Beratung von Familien" in full.description
    assert "Arbeitszeit: Vollzeit" in full.description
    assert "Ort: Beispielhausen\n" in full.description  # without "Karte anschauen"
    assert full.job_types == ["fixed_term"]
    assert (full.latitude, full.longitude) == (52.5, 13.4)
    assert full.employer_url == "https://fake-bewerbung.example/job/1"
    assert full.salary_text == "E 13 TVöD"
    # The page's closing day, open until its end.
    assert full.closes_at == datetime(2026, 10, 23, 21, 59, tzinfo=UTC)


def test_job_types_and_pay_grades():
    source = servicebund.ServiceBundSource()
    career_track = page(duration="Unbefristet", pay="Mittlerer Dienst")
    permanent = source.load_details(summary_job(), context(
        lambda request: httpx.Response(200, text=career_track)))
    assert permanent.job_types == ["full_time_permanent"]
    assert permanent.salary_text is None  # a career track, not a pay grade
    part = source.load_details(summary_job(), context(
        lambda request: httpx.Response(200, text=page(hours="Teilzeit", duration="Unbefristet"))))
    assert part.job_types == ["part_time"]


def test_a_page_without_an_ad_keeps_the_summary():
    job = summary_job()
    ctx = context(lambda request: httpx.Response(200, text=page(text=False)))
    assert servicebund.ServiceBundSource().load_details(job, ctx) == job


def test_only_the_first_pages_are_read_because_of_the_crawl_delay():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=page())

    source, ctx = servicebund.ServiceBundSource(), context(handler)
    results = [source.load_details(summary_job(), ctx)
               for _ in range(servicebund.MAX_FULL_ADS + 3)]
    assert len(requests) == servicebund.MAX_FULL_ADS
    assert not results[-1].description_is_complete
    # robots.txt asks for 30 seconds between requests.
    assert SITE_INTERVALS["www.service.bund.de"] == 30.0
