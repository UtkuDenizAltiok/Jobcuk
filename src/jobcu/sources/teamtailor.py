"""Teamtailor career sites, through the RSS feed every Teamtailor career site publishes.
Checked 2026-09-21.

`GET https://{board}.teamtailor.com/jobs.rss` (or `https://{custom domain}/jobs.rss` for
companies with their own address) lists every published job with its full ad, publication
time, remote status and places with city and country. No key. robots.txt allows the job pages
and the feed for every crawler; only accounts, messages and internal jobs are closed.
"""

from collections.abc import Iterator
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from jobcu.placenames import OTHER, countries_in
from jobcu.sources.base import FoundJob, SourceContext, SourceError
from jobcu.sources.careers import CareerSystemSource, Employer
from jobcu.text import html_to_text

TT = "{https://teamtailor.com/locations}"
WORK_MODES = {"fully": "remote", "remote": "remote", "hybrid": "hybrid", "none": "on_site",
              "onsite": "on_site"}


def feed_url(board: str) -> str:
    """A board is the company's Teamtailor name, or its own career-site address."""
    host = board if "." in board else f"{board}.teamtailor.com"
    return f"https://{host}/jobs.rss"


class TeamtailorSource(CareerSystemSource):
    id = "teamtailor"
    name = "Company career sites (Teamtailor)"
    system = "teamtailor"
    # Every company has its own address, so a few can be read at once (the pace per address
    # stays polite).
    parallel = 4

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None,
                  terms=None) -> Iterator[FoundJob]:
        response = self.get(feed_url(employer.board), ctx)
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as exc:
            raise SourceError(f"{self.name} didn't answer with a job list.") from exc
        for item in root.iterfind("channel/item"):
            yield to_found_job(item, employer)


def to_found_job(item, employer: Employer) -> FoundJob:
    places = []
    for place in item.iterfind(f"{TT}locations/{TT}location"):
        city, country = place.findtext(f"{TT}city"), place.findtext(f"{TT}country")
        places.append(", ".join(part.strip() for part in (city, country) if part and part.strip()))
    location = "; ".join(place for place in places if place) or None
    codes = countries_in(location) - {OTHER} if location else set()
    try:
        posted = parsedate_to_datetime(item.findtext("pubDate") or "")
    except (TypeError, ValueError):
        posted = None
    return FoundJob(
        source="teamtailor",
        source_job_id=f"{employer.board}/{item.findtext('guid') or item.findtext('link')}",
        url=(item.findtext("link") or "").strip(),
        title=(item.findtext("title") or "").strip(),
        company=employer.name,
        location_text=location,
        country=next(iter(codes)) if len(codes) == 1 else None,
        posted_at=posted if posted and posted.tzinfo else None,
        date_precision="exact" if posted and posted.tzinfo else "unknown",
        description=html_to_text(item.findtext("description")),
        description_is_complete=True,
        work_mode=WORK_MODES.get((item.findtext("remoteStatus") or "").strip().lower()),
    )
