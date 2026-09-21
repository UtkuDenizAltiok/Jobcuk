"""Recruitee career sites, through Recruitee's public Careers Site API (documented for building
career pages; no key). Checked 2026-09-17.

`GET https://{board}.recruitee.com/api/offers/` returns every published job with its full ad,
publication time, places with country codes, and employment type in one answer.
"""

from collections.abc import Iterator

from jobcu.freshness import parse_iso
from jobcu.sources.base import FoundJob, SourceContext
from jobcu.sources.careers import CareerSystemSource, Employer, job_types_from_text
from jobcu.text import html_to_text, tidy


class RecruiteeSource(CareerSystemSource):
    id = "recruitee"
    name = "Company career sites (Recruitee)"
    system = "recruitee"
    parallel = 4

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None,
                  terms=None) -> Iterator[FoundJob]:
        data = self.get_json(f"https://{employer.board}.recruitee.com/api/offers/", ctx)
        for item in data.get("offers") or []:
            if item.get("status", "published") == "published":
                yield to_found_job(item, employer)


def to_found_job(item: dict, employer: Employer) -> FoundJob:
    places = item.get("locations") or [item]
    location = "; ".join(
        ", ".join(part for part in (place.get("city"), place.get("country")) if part)
        for place in places
    ) or item.get("location")
    codes = {(place.get("country_code") or "").upper() for place in places} - {""}
    published = (item.get("published_at") or item.get("created_at") or "").replace(" UTC", "Z")
    posted = parse_iso(published.replace(" ", "T")) if published else None
    if item.get("remote"):
        work_mode = "remote"
    elif item.get("hybrid"):
        work_mode = "hybrid"
    elif item.get("on_site"):
        work_mode = "on_site"
    else:
        work_mode = None
    parts = [html_to_text(item.get("description")), html_to_text(item.get("requirements"))]
    return FoundJob(
        source="recruitee",
        source_job_id=f"{employer.board}/{item.get('id')}",
        url=item.get("careers_url") or "",
        title=(item.get("title") or "").strip(),
        company=employer.name,
        location_text=location or None,
        country=next(iter(codes)) if len(codes) == 1 else None,
        posted_at=posted,
        date_precision="exact" if posted else "unknown",
        description=tidy("\n\n".join(p for p in parts if p)),
        description_is_complete=True,
        job_types=job_types_from_text(item.get("employment_type_code")),
        work_mode=work_mode,
    )
