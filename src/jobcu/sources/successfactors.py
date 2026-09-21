"""SAP SuccessFactors career sites (Career Site Builder), through the sitemap each site
publishes for search engines at `/sitemap.xml`. Checked 2026-09-21.

The sitemap comes in two forms:

- **a job feed** (SAP's own site): RSS with every open job's full ad and its place ("Walldorf,
  DE, 69190"), but no posting date;
- **a list of job pages** (Schaeffler, Festo, SICK, KUKA, ZF and most others):
  `/job/{Town}-{Title}-{postcode}/{id}/`, all with the same "last changed" day.

Either way, the posting date is only on the job's own page (`itemprop="datePosted"`), next to
the place, the title and the full ad. So in a search Jobcu first keeps the jobs whose title
matches the search words (and, in a feed, that are in a country searched), and only opens those
pages. A date read in the last three days comes from what Jobcu remembers.

The usual robots.txt closes `/services/` (where SuccessFactors' own RSS search lives) and allows
the job pages and the sitemap; Jobcu checks each company's robots.txt all the same. Big
companies' sitemaps are large (SAP's feed: 16 MB for about 1,000 jobs), so they aren't kept in
memory after reading.
"""

import dataclasses
import html
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

from lxml import html as lxml_html
from lxml.etree import ParserError

from jobcu import places as place_list
from jobcu.countries import COUNTRIES
from jobcu.freshness import day_at_utc, parse_iso
from jobcu.jobposting import find_job_posting
from jobcu.placenames import OTHER
from jobcu.sources.base import FoundJob, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted
from jobcu.sources.careers import CareerSystemSource, Employer
from jobcu.sources.matching import matches_terms
from jobcu.text import html_to_text

G = "{http://base.google.com/ns/1.0}"
SITEMAP = "{http://www.google.com/schemas/sitemap/0.9}"
_DATE_POSTED = re.compile(r"itemprop=[\"']datePosted[\"'][^>]*content=[\"']([^\"']+)[\"']", re.I)
_ZIP = re.compile(r"^[A-Z0-9 -]*\d[A-Z0-9 -]*$")
_JOB_PATH = re.compile(r"/job/([^/]+)/(\d+)/?$")


class SuccessFactorsSource(CareerSystemSource):
    id = "successfactors"
    name = "Company career sites (SuccessFactors)"
    system = "successfactors"
    # Every company has its own address, so a few can be read at once.
    parallel = 4

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None,
                  terms=None) -> Iterator[FoundJob]:
        sitemap = f"https://{employer.board}/sitemap.xml"
        if not self.allowed(sitemap, ctx):
            raise SourceError(f"{employer.board} asks automated tools not to read its job list.")
        response = self.get(sitemap, ctx, cache=False)
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as exc:
            raise SourceError(f"{self.name} didn't answer with a job list.") from exc
        languages = {"en"}
        for code in countries or ():
            languages.update(COUNTRIES[code].ad_languages)
        if root.tag == "rss":
            for item in root.iterfind("channel/item"):
                job = from_feed(item, employer)
                if terms is None:
                    yield job  # the directory check: every job, no pages opened
                elif (not countries or job.country in countries) and matches_terms(
                        terms, languages, job.title, job.description):
                    yield self._dated(job, ctx)
            return
        for loc in root.iterfind(f"{SITEMAP}url/{SITEMAP}loc"):
            job = from_page_address((loc.text or "").strip(), employer)
            if job is None:
                continue
            if terms is None:
                yield job
            elif matches_terms(terms, languages, job.title):
                full = self._from_page(job, ctx)
                if full is not None:
                    yield full

    def _page(self, job: FoundJob, ctx: SourceContext) -> str | None:
        if not self.allowed(job.url, ctx):
            return None
        try:
            return self.get(job.url, ctx, cache=False).text
        except (SourceError, BudgetExhausted):
            return None

    def _dated(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        """A feed job with its posting day, from memory or from its page."""
        # Imported here: the job memory itself imports the sources (through dedupe).
        from jobcu import jobstore

        known = jobstore.remembered_ad(job)
        if known is not None and known.posted_at:
            return dataclasses.replace(known, date_precision="day")
        posted = date_posted(self._page(job, ctx) or "")
        if posted is None:
            return job  # kept with an unknown date rather than lost
        dated = dataclasses.replace(job, posted_at=day_at_utc(posted.date()),
                                    date_precision="day")
        jobstore.remember_ad(dated)
        return dated

    def _from_page(self, job: FoundJob, ctx: SourceContext) -> FoundJob | None:
        """Everything about a listed job from its own page, or None if it can't be read."""
        page = self._page(job, ctx)
        if page is None:
            return None
        found = read_page(page)
        location, code = place(found.get("place") or "")
        posted = date_posted(page)
        return dataclasses.replace(
            job,
            title=found.get("title") or job.title,
            company=found.get("company") or job.company,
            location_text=location or job.location_text,
            country=code or job.country,
            posted_at=day_at_utc(posted.date()) if posted else None,
            date_precision="day" if posted else "unknown",
            description=found.get("description") or "",
            description_is_complete=bool(found.get("description")),
        )


def date_posted(page: str) -> datetime | None:
    """The posting day a job page gives search engines, in either of the usual forms."""
    match = _DATE_POSTED.search(page or "")
    if match:
        text = match.group(1).strip()
        try:  # "Wed Sep 09 02:00:00 UTC 2026"
            return datetime.strptime(text, "%a %b %d %H:%M:%S %Z %Y").replace(tzinfo=UTC)
        except ValueError:
            parsed = parse_iso(text)
            if parsed:
                return parsed
    posting = find_job_posting(page)
    return posting.date_posted if posting else None


def read_page(page: str) -> dict[str, str]:
    """Title, place, company and ad text from the data a job page marks for search engines."""
    try:
        doc = lxml_html.document_fromstring(page or "<html></html>")
    except (ParserError, ValueError):
        return {}

    def first(xpath: str) -> str:
        found = doc.xpath(xpath)
        return found[0].strip() if found and isinstance(found[0], str) else ""

    blocks = doc.xpath('//*[@itemprop="description"]')
    description = html_to_text(lxml_html.tostring(blocks[0], encoding="unicode")) if blocks else ""
    return {
        "title": " ".join(" ".join(doc.xpath('//*[@itemprop="title"]//text()')).split()),
        "place": first('//*[@itemprop="streetAddress"]/@content')
                 or first('//*[@itemprop="addressLocality"]/@content'),
        "company": first('//*[@itemprop="hiringOrganization"]/@content'),
        "description": description,
    }


def place(text: str) -> tuple[str | None, str | None]:
    """("Walldorf, Germany", "DE") from "Walldorf, DE, 69190"; the country is the last
    two-letter code ("Burlington, MA, US, 01803" is in the US)."""
    parts = [part.strip() for part in (text or "").split(",") if part.strip()]
    written = next((part for part in reversed(parts) if re.fullmatch(r"[A-Z]{2}", part)), None)
    code = "GB" if written == "UK" else written
    town = [part for part in parts if part != written and not _ZIP.match(part)]
    if code in COUNTRIES:
        town.append(COUNTRIES[code].name)
    return (", ".join(town) or None), code


def from_feed(item, employer: Employer) -> FoundJob:
    raw_place = item.findtext(f"{G}location") or ""
    location, code = place(raw_place)
    title = (item.findtext("title") or "").strip()
    # Titles end with the place in brackets: "Hardware Engineer (Walldorf, DE, 69190)".
    if raw_place and title.endswith(f"({raw_place})"):
        title = title[: -len(raw_place) - 2].strip()
    job_id = (item.findtext("guid") or item.findtext(f"{G}id") or "").strip()
    return FoundJob(
        source="successfactors",
        source_job_id=f"{employer.board}/{job_id}",
        url=(item.findtext("link") or "").strip(),
        title=title,
        company=(item.findtext(f"{G}employer") or "").strip() or employer.name,
        location_text=location,
        country=code,
        description=html_to_text(html.unescape(item.findtext("description") or "")),
        description_is_complete=True,
    )


def from_page_address(url: str, employer: Employer) -> FoundJob | None:
    """What a job page's address tells: "/job/Bühl-Praktikum-HR-(dmw)-77815/1108248501/".

    The words are the town and the title, which is enough to match the search words. The town
    is looked up in the supported countries only to learn where a company hires (the directory
    check); in a search the page itself says where the job is.
    """
    match = _JOB_PATH.search(urlsplit(url).path)
    if not match:
        return None
    words = [word for word in unquote(match.group(1)).split("-") if word]
    if words and _ZIP.match(words[-1]):
        words = words[:-1]
    town = _leading_town(words)
    return FoundJob(
        source="successfactors",
        source_job_id=f"{employer.board}/{match.group(2)}",
        url=url,
        title=" ".join(words),
        company=employer.name,
        location_text=town.name if town else None,
        country=town.country if town else OTHER,
    )


def _leading_town(words: list[str]):
    """The town the address starts with ("Frankfurt-am-Main-…"), in a supported country."""
    for length in (3, 2, 1):
        name = " ".join(words[:length])
        towns = [town for code in COUNTRIES if (town := place_list.find(name, code))]
        if towns:
            return max(towns, key=lambda town: town.people)
    return None
