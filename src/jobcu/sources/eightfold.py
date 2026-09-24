"""Eightfold career sites (Infineon, Qualcomm, Ericsson, Vodafone and others), checked
2026-09-24.

An Eightfold career site publishes a sitemap of every open job, `https://{host}/careers/
sitemap.xml?domain={domain}`, with the time each job last changed and its title and place in the
address ("/careers/job/563808972057566-staff-specialist-scenario-planning-dresden"). Each job's
page carries the standard job data (schema.org JobPosting): the exact posting time, the place,
the full ad and the closing date. Their robots.txt closes most of the site but explicitly allows
`/careers` for every crawler.

Jobcu reads the sitemap, keeps the jobs changed since the window began whose address matches
the search words, and opens only those pages. The board is written "host/domain", for example
"jobs.infineon.com/infineon.com".
"""

import re
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterator
from datetime import timedelta

from jobcu.freshness import parse_iso
from jobcu.jobposting import find_job_posting
from jobcu.sources.base import FoundJob, SourceContext, SourceError
from jobcu.sources.careers import CareerSystemSource, Employer
from jobcu.sources.matching import term_matches

_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_JOB = re.compile(r"/careers/job/(?P<id>\d+)-?(?P<slug>[^?]*)")


class EightfoldSource(CareerSystemSource):
    id = "eightfold"
    name = "Company career sites (Eightfold)"
    system = "eightfold"
    parallel = 4  # every employer has its own host

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None,
                  terms=None) -> Iterator[FoundJob]:
        host, _, domain = employer.board.partition("/")
        sitemap = f"https://{host}/careers/sitemap.xml?domain={domain or host}"
        if not self.allowed(sitemap, ctx):
            raise SourceError(f"{employer.name}'s career site doesn't allow automated reading.")
        try:
            root = ElementTree.fromstring(self.get(sitemap, ctx).text)
        except ElementTree.ParseError:
            raise SourceError(f"{employer.name}'s job list couldn't be read.") from None
        since = start - timedelta(days=1) if start else None
        for entry in root.iter(f"{_NS}url"):
            url = (entry.findtext(f"{_NS}loc") or "").strip()
            found = _JOB.search(url)
            if not found:
                continue
            words = found.group("slug").replace("-", " ").strip()
            changed = parse_iso((entry.findtext(f"{_NS}lastmod") or "").strip())
            if start is None and terms is None:
                # The directory check: the address's words say enough about the place.
                yield FoundJob(source="eightfold", source_job_id=f"{host}/{found.group('id')}",
                               url=url, title=words, company=employer.name,
                               location_text=words)
                continue
            if since and changed and changed < since:
                continue
            if terms and not any(term_matches(term.text, words) for term in terms
                                 if term.kind == "job_title"):
                continue
            job = self._job(url, found.group("id"), host, employer, ctx)
            if job is not None:
                yield job

    def _job(self, url: str, job_id: str, host: str, employer: Employer,
             ctx: SourceContext) -> FoundJob | None:
        try:
            posting = find_job_posting(self.get(url, ctx).text)
        except SourceError:
            return None
        if posting is None or not posting.title:
            return None
        return FoundJob(
            source="eightfold",
            source_job_id=f"{host}/{job_id}",
            url=url,
            title=posting.title,
            company=employer.name,
            location_text=posting.location_text,
            posted_at=posting.date_posted,
            date_precision=("exact" if posting.date_has_time else "day")
            if posting.date_posted else "unknown",
            description=posting.description,
            description_is_complete=bool(posting.description),
            job_types=posting.job_types,
            work_mode="remote" if posting.remote else None,
            closes_at=posting.valid_through,
        )
