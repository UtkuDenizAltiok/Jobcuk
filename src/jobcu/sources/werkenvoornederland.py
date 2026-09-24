"""Werken voor Nederland: the Dutch central government's own job site (ministries, agencies,
courts, the tax office, Rijkswaterstaat…), checked 2026-09-24.

Its sitemap lists every open job (about 1,300) with the time it last changed, and each job's
address carries its title ("/vacatures/beleidsmedewerker-netwerkontwikkeling-ov-en-spoor-IM-
2026-7658"). Jobcu matches the search words against those titles and opens only the matching
jobs' pages, which carry the standard job data (schema.org JobPosting: posting date, place,
employer, contract, closing date, salary) and the full ad. robots.txt closes only the login and
allows ten requests a second.
"""

import re
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterator
from datetime import timedelta

import httpx
import trafilatura

from jobcu.freshness import day_at_utc, freshness, parse_iso, window_start
from jobcu.jobposting import find_job_posting
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.http import Blocked
from jobcu.sources.matching import matches_places, matches_terms
from jobcu.text import tidy

SITE = "https://www.werkenvoornederland.nl"
SITEMAP = f"{SITE}/sitemap-vacatures.xml"
LIMITS = Limits(per_search=80)
_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
# "…/vacatures/{title words}-{organisation}-{year}-{number}"
_ADDRESS = re.compile(r"/vacatures/(?P<slug>.+?)-(?P<org>[A-Za-z]+)-(?P<year>\d{4})-(?P<num>\d+)$")


class WerkenVoorNederlandSource(JobSource):
    id = "werkenvoornederland"
    name = "Werken voor Nederland (Dutch government)"
    kind = "employer"
    countries = frozenset({"NL"})

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        self._budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        languages = {"en", "nl"}
        try:
            for url, title in self._changed_since(start - timedelta(days=1), ctx):
                if ctx.should_stop():
                    return
                if not matches_terms(query.terms, languages, title):
                    continue
                job = self._job(url, title, ctx)
                if job is None or freshness(job.posted_at, job.date_precision, start) == (
                        "too_old"):
                    continue
                if matches_places(query.places, "NL", job.location_text):
                    yield job
        except BudgetExhausted as exc:
            ctx.report.status = "partial"
            ctx.report.message = exc.message

    def _changed_since(self, since, ctx: SourceContext) -> list[tuple[str, str]]:
        """The sitemap's jobs changed since then, with the title words from their address."""
        try:
            root = ElementTree.fromstring(self._get(SITEMAP, ctx))
        except ElementTree.ParseError:
            raise SourceError("Werken voor Nederland didn't answer with its job list.") from None
        found = []
        for entry in root.iter(f"{_NS}url"):
            url = (entry.findtext(f"{_NS}loc") or "").strip()
            changed = parse_iso((entry.findtext(f"{_NS}lastmod") or "").strip())
            address = _ADDRESS.search(url)
            if not address or (changed is not None and changed < since):
                continue
            found.append((url, address.group("slug").replace("-", " ")))
        return found

    def _job(self, url: str, title: str, ctx: SourceContext) -> FoundJob | None:
        try:
            page = self._get(url, ctx)
        except (SourceError, Blocked):
            return None
        return from_page(url, title, page)

    def _get(self, url: str, ctx: SourceContext) -> str:
        self._budget.spend()
        ctx.report.requests += 1
        try:
            response = ctx.http.get(url, cache=False)
        except httpx.HTTPError as exc:
            raise SourceError("Werken voor Nederland couldn't be reached.") from exc
        if response.status_code == 429:
            raise BudgetExhausted("Werken voor Nederland: asked Jobcu to slow down for now.")
        if response.status_code != 200:
            raise SourceError(
                f"Werken voor Nederland answered with a problem (code {response.status_code}).")
        return response.text


def from_page(url: str, title: str, page: str) -> FoundJob | None:
    """The job from its page: the standard job data for the facts, the page for the ad."""
    posting = find_job_posting(page)
    if posting is None:
        return None
    text = tidy(trafilatura.extract(page, include_comments=False, include_tables=True,
                                    favor_recall=True) or "")
    description = text if len(text) > len(posting.description) else posting.description
    posted = posting.date_posted
    if posted is not None and not posting.date_has_time:
        posted = day_at_utc(posted.date())
    number = _ADDRESS.search(url)
    return FoundJob(
        source="werkenvoornederland",
        source_job_id=f"{number.group('org')}-{number.group('year')}-{number.group('num')}"
        if number else url,
        url=url,
        title=posting.title or title,
        company=(posting.company or "").strip() or None,
        location_text=posting.location_text,
        country="NL",
        posted_at=posted,
        date_precision=("exact" if posting.date_has_time else "day") if posted else "unknown",
        description=description,
        description_is_complete=len(text) > len(posting.description),
        job_types=posting.job_types,
        closes_at=posting.valid_through,
    )
