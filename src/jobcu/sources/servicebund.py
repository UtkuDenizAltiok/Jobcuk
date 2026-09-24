"""service.bund.de: the German public sector's job portal (Bundesverwaltungsamt), checked
2026-09-24.

Federal, state and municipal employers, universities, research institutes, courts and prisons
publish their jobs here: clerks, social workers, lawyers, teachers, trades, housekeeping,
research and engineering. About two thirds of them aren't on the Bundesagentur's Jobbörse.

The site offers an RSS feed of the newest 500 jobs for feed readers, which reaches back about
two and a half days, so one request covers a 24- or 48-hour search. Jobcu matches the titles
and places on its own side. The full ad is on each job's page; robots.txt asks for 30 seconds
between requests, so only the first few jobs still in the running are read in full, and the
rest are read online by the person's AI like other summaries.
"""

import dataclasses
import html
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx
from lxml import etree
from lxml import html as lxml_html
from lxml.etree import ParserError

from jobcu.freshness import day_at_utc, freshness, window_start
from jobcu.placenames import OTHER, countries_in
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.http import Blocked
from jobcu.sources.matching import matches_places, matches_terms
from jobcu.text import html_to_text, tidy

SITE = "https://www.service.bund.de"
FEED = f"{SITE}/Content/Globals/Functions/RSSFeed/RSSGenerator_Stellen.xml"
# robots.txt: "Crawl-delay: 30". Twelve pages take six minutes; the jobs after them keep their
# summary and are read online by the person's AI when they score well (jobplace.py).
MAX_FULL_ADS = 12
GERMAN_TIME = ZoneInfo("Europe/Berlin")
_POSTCODE_PLACE = re.compile(r"^\s*(\d{5})\s+(.+)$")
# A pay grade worth showing: "E 13 TVöD", "A 9", "EG 11", "TV-L E 10", "W 2".
_PAY_GRADE = re.compile(r"\b(?:E|A|W|EG|TV-?L|TVöD)\s*-?\s*\d", re.IGNORECASE)


class ServiceBundSource(JobSource):
    id = "servicebund"
    name = "service.bund.de (public sector)"
    kind = "job_board"
    countries = frozenset({"DE"})

    def __init__(self) -> None:
        self._full_ads_read = 0

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        start = window_start(query.started_at, query.posted_within_hours)
        items = parse_feed(self._get(FEED, ctx))
        jobs = [job for job in (to_found_job(item, query.countries) for item in items) if job]
        dated = [job.posted_at for job in jobs if job.posted_at]
        if len(items) >= 400 and dated and min(dated) > start:
            # The feed holds only the newest jobs; say so rather than pretend to be complete.
            ctx.report.status = "partial"
            ctx.report.message = (
                "service.bund.de's feed reaches back only to "
                f"{min(dated).astimezone(GERMAN_TIME):%d %B}, so older public-sector jobs "
                "in the window weren't seen."
            )
        languages = {"en", "de"}
        for job in jobs:
            if freshness(job.posted_at, job.date_precision, start) == "too_old":
                continue
            if not matches_terms(query.terms, languages, job.title, job.description):
                continue
            if not matches_places(query.places, job.country or "DE", job.location_text):
                continue
            yield job

    def load_details(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        if self._full_ads_read >= MAX_FULL_ADS:
            return job
        self._full_ads_read += 1
        try:
            page = self._get(job.url, ctx)
        except (SourceError, Blocked):
            return job
        return apply_details(job, page)

    def _get(self, url: str, ctx: SourceContext) -> str:
        ctx.report.requests += 1
        try:
            response = ctx.http.get(url, cache=False)
        except httpx.HTTPError as exc:
            raise SourceError("service.bund.de couldn't be reached.") from exc
        if response.status_code != 200:
            raise SourceError(
                f"service.bund.de answered with a problem (code {response.status_code})."
            )
        return response.text


def parse_feed(xml: str) -> list[dict]:
    """The feed's items as plain values: title, link, date and the description's facts."""
    try:
        root = etree.fromstring(xml.encode("utf-8"), parser=etree.XMLParser(recover=True))
    except (etree.XMLSyntaxError, ValueError):
        raise SourceError("service.bund.de didn't answer with its job feed.") from None
    if root is None:
        raise SourceError("service.bund.de didn't answer with its job feed.")
    items = []
    for item in root.iter("item"):
        facts = _description_facts(item.findtext("description") or "")
        items.append({
            "title": tidy(item.findtext("title") or ""),
            "link": (item.findtext("link") or "").strip(),
            "guid": (item.findtext("guid") or "").strip(),
            "pub_date": (item.findtext("pubDate") or "").strip(),
            **facts,
        })
    return items


def _description_facts(markup: str) -> dict:
    """ "Arbeitgeber: <strong>…</strong>", "Ort: <strong>65173 Wiesbaden</strong>" and
    "Bewerbungsfrist: <strong>23.10.2026 23:59</strong>" from an item's description."""
    facts = {}
    for label, key in (("Arbeitgeber", "employer"), ("Ort", "place"),
                       ("Bewerbungsfrist", "closes")):
        found = re.search(rf"{label}:\s*<strong>(.*?)</strong>", markup, re.DOTALL)
        # The feed escapes umlauts inside its CDATA ("Universit&#228;t").
        facts[key] = html_to_text(html.unescape(found.group(1))) if found else ""
    return facts


def _posted(text: str) -> tuple[datetime | None, str]:
    """The feed's date. Midnight exactly means only the day is known."""
    try:
        value = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None, "unknown"
    if value.tzinfo is None:
        value = value.replace(tzinfo=GERMAN_TIME)
    local = value.astimezone(GERMAN_TIME)
    if (local.hour, local.minute, local.second) == (0, 0, 0):
        return day_at_utc(local.date()), "day"
    return value.astimezone(UTC), "exact"


def _without_fragment(url: str) -> str:
    """The feed adds "#track=feed-jobs" to every link."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _place_and_country(place: str, searched: list[str]) -> tuple[str | None, str | None]:
    """ "65173 Wiesbaden" is a German town. A place without a German postcode (a job at an
    embassy, say) keeps its own country when that country is being searched."""
    found = _POSTCODE_PLACE.match(place or "")
    if found:
        return found.group(2).strip(), "DE"
    countries = countries_in(place) - {OTHER}
    country = next((code for code in searched if code in countries), None)
    return (place.strip() or None), country


def to_found_job(item: dict, searched: list[str]) -> FoundJob | None:
    """One feed item, or None when it lies outside the countries searched."""
    location, country = _place_and_country(item.get("place", ""), searched)
    if country is None:
        return None
    url = _without_fragment(item.get("link") or item.get("guid") or "")
    job_id = re.search(r"/(\d+)\.html", url)
    posted, precision = _posted(item.get("pub_date", ""))
    lines = [f"Arbeitgeber: {item['employer']}" if item.get("employer") else "",
             f"Ort: {item['place']}" if item.get("place") else "",
             f"Bewerbungsfrist: {item['closes']}" if item.get("closes") else ""]
    return FoundJob(
        source="servicebund",
        source_job_id=job_id.group(1) if job_id else url,
        url=url,
        title=item.get("title", ""),
        company=item.get("employer") or None,
        location_text=location,
        country=country,
        posted_at=posted,
        date_precision=precision,
        description="\n".join(line for line in lines if line),
    )


def _document(markup: str):
    try:
        return lxml_html.document_fromstring(markup or "<html></html>")
    except (ParserError, ValueError):
        return lxml_html.document_fromstring("<html></html>")


def _short_facts(document) -> dict[str, str]:
    """The "Kurzinfo" list: Arbeitszeit, Anstellungsdauer, Bewerbungsfrist, Entgeltgruppe…"""
    facts = {}
    for term in document.xpath("//section[contains(@class, 'shortlist')]//dt"):
        value = term.getnext()
        if value is not None and value.tag == "dd":
            # The place carries a "Karte anschauen" (show map) link.
            text = tidy(value.text_content()).replace("Karte anschauen", "")
            facts[tidy(term.text_content())] = tidy(text)
    return facts


def _job_types(facts: dict[str, str]) -> list[str]:
    hours = facts.get("Arbeitszeit", "").lower()
    duration = facts.get("Anstellungsdauer", "").lower()
    types = []
    if "unbefristet" in duration:
        if "vollzeit" in hours:
            types.append("full_time_permanent")
    elif "befristet" in duration:
        types.append("fixed_term")
    if "teilzeit" in hours:
        types.append("part_time")
    return types


def _employer_link(document) -> str | None:
    """The employer's own copy of the ad ("Stellenangebot (HTML-Seite)"), usually in its
    application system."""
    for link in document.xpath("//a[contains(normalize-space(.), 'Stellenangebot (HTML')]"):
        href = (link.get("href") or "").strip()
        if href.startswith(("https://", "http://")) and "service.bund.de" not in href:
            return href
    return None


def apply_details(job: FoundJob, page: str) -> FoundJob:
    """The full ad and its facts from the job's own page. Without an ad text the job keeps its
    summary, so a page that changed never makes things worse."""
    start, end = page.find("<!--Tätigkeit einfügen-->"), page.find("<!--Tätigkeit ende-->")
    if start < 0 or end < start:
        return job
    text = html_to_text(page[start:end])
    if not text:
        return job
    document = _document(page)
    facts = _short_facts(document)
    closes = facts.get("Bewerbungsfrist")
    pay = facts.get("Laufbahn / Entgeltgruppe", "")
    place = facts.get("Ort") or job.location_text
    header = "\n".join(line for line in (
        f"Arbeitgeber: {job.company}" if job.company else "",
        f"Ort: {place}" if place else "",
        f"Arbeitszeit: {facts['Arbeitszeit']}" if facts.get("Arbeitszeit") else "",
        f"Anstellungsdauer: {facts['Anstellungsdauer']}" if facts.get("Anstellungsdauer") else "",
        f"Laufbahn / Entgeltgruppe: {pay}" if pay else "",
        f"Bewerbungsfrist: {closes}" if closes else "",
    ) if line)
    latitude, longitude = job.latitude, job.longitude
    for spot in document.xpath("//*[@id='location-map'][@data-lat][@data-lon]")[:1]:
        try:
            latitude, longitude = float(spot.get("data-lat")), float(spot.get("data-lon"))
        except ValueError:
            pass
    employer_url = _employer_link(document)
    return dataclasses.replace(
        job,
        description=f"{header}\n\n{text}" if header else text,
        description_is_complete=True,
        job_types=_job_types(facts) or job.job_types,
        latitude=latitude,
        longitude=longitude,
        employer_url=urljoin(SITE, employer_url) if employer_url else job.employer_url,
        salary_text=pay if _PAY_GRADE.search(pay) else job.salary_text,
    )
