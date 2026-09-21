"""Lever career sites, through Lever's public Postings API (documented for building career
pages; no key). Checked 2026-09-17: robots.txt allows everything with a 1-second crawl delay.

`GET /v0/postings/{company}?mode=json` returns every job with its full ad, creation time,
country code and workplace type. Companies on Lever's EU servers use api.eu.lever.co; the
directory marks them as "eu/{company}".
"""

from collections.abc import Iterator
from datetime import UTC, datetime

from jobcu.sources.base import FoundJob, SourceContext
from jobcu.sources.careers import (
    CareerSystemSource,
    Employer,
    job_types_from_text,
    work_mode_from_text,
)
from jobcu.text import html_to_text, tidy

API = {"global": "https://api.lever.co/v0/postings", "eu": "https://api.eu.lever.co/v0/postings"}


def _address(board: str) -> str:
    region, _, company = board.rpartition("/")
    return f"{API['eu' if region == 'eu' else 'global']}/{company}"


class LeverSource(CareerSystemSource):
    id = "lever"
    name = "Company career sites (Lever)"
    system = "lever"

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None,
                  terms=None) -> Iterator[FoundJob]:
        data = self.get_json(_address(employer.board), ctx, params={"mode": "json"})
        for item in data if isinstance(data, list) else []:
            yield to_found_job(item, employer)


def to_found_job(item: dict, employer: Employer) -> FoundJob:
    categories = item.get("categories") or {}
    locations = categories.get("allLocations") or [categories.get("location")]
    location = "; ".join(loc for loc in locations if loc) or None
    created = item.get("createdAt")
    posted = datetime.fromtimestamp(created / 1000, UTC) if isinstance(created, int) else None
    parts = [item.get("descriptionPlain") or html_to_text(item.get("description"))]
    for section in item.get("lists") or []:
        parts.append(f"{section.get('text') or ''}\n{html_to_text(section.get('content'))}")
    parts.append(item.get("additionalPlain") or html_to_text(item.get("additional")))
    workplace = (item.get("workplaceType") or "").replace("-", "_").replace("onsite", "on_site")
    country = (item.get("country") or "").upper() or None
    return FoundJob(
        source="lever",
        source_job_id=str(item.get("id")),
        url=item.get("hostedUrl") or "",
        title=(item.get("text") or "").strip(),
        company=employer.name,
        location_text=location,
        # Lever gives one country code even for jobs in several places, so only a single
        # place is trusted; otherwise the location text decides.
        country=country if len(locations) <= 1 else None,
        posted_at=posted,
        date_precision="exact" if posted else "unknown",
        description=tidy("\n\n".join(p for p in parts if p)),
        description_is_complete=True,
        job_types=job_types_from_text(categories.get("commitment")),
        work_mode=workplace if workplace in ("remote", "hybrid", "on_site")
        else work_mode_from_text(location),
    )
