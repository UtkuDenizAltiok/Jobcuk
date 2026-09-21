"""Ashby career sites, through Ashby's public Job Postings API (documented for building career
pages; no key). Checked 2026-09-17.

`GET /posting-api/job-board/{board}` returns every listed job with its full ad, publication
time, location, country and employment type in one answer. Answers can be large (several MB
for companies with hundreds of jobs), so the directory only lists companies worth it.
"""

from collections.abc import Iterator

from jobcu.freshness import parse_iso
from jobcu.sources.base import FoundJob, SourceContext
from jobcu.sources.careers import (
    CareerSystemSource,
    Employer,
    job_types_from_text,
    work_mode_from_text,
)
from jobcu.text import html_to_text, tidy

API = "https://api.ashbyhq.com/posting-api/job-board"
_WORKPLACES = {"remote": "remote", "hybrid": "hybrid", "onsite": "on_site", "on_site": "on_site"}


class AshbySource(CareerSystemSource):
    id = "ashby"
    name = "Company career sites (Ashby)"
    system = "ashby"

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None,
                  terms=None) -> Iterator[FoundJob]:
        data = self.get_json(f"{API}/{employer.board}", ctx)
        for item in data.get("jobs") or []:
            if item.get("isListed", True):
                yield to_found_job(item, employer)


def to_found_job(item: dict, employer: Employer) -> FoundJob:
    places = [item.get("location")]
    countries = [((item.get("address") or {}).get("postalAddress") or {}).get("addressCountry")]
    for extra in item.get("secondaryLocations") or []:
        places.append(extra.get("location"))
        countries.append(((extra.get("address") or {}).get("postalAddress") or {})
                         .get("addressCountry"))
    # The location name alone can be vague ("Office"), so the country is added to it.
    location = "; ".join(
        ", ".join(dict.fromkeys(part for part in (place, country) if part))
        for place, country in zip(places, countries, strict=True)
        if place or country
    ) or None
    published = item.get("publishedAt")
    workplace = (item.get("workplaceType") or "").lower().replace("-", "")
    return FoundJob(
        source="ashby",
        source_job_id=str(item.get("id")),
        url=item.get("jobUrl") or "",
        title=(item.get("title") or "").strip(),
        company=employer.name,
        location_text=location,
        posted_at=parse_iso(published),
        date_precision="exact" if published else "unknown",
        description=tidy(item.get("descriptionPlain") or html_to_text(item.get("descriptionHtml"))),
        description_is_complete=True,
        job_types=job_types_from_text(item.get("employmentType")),
        work_mode=_WORKPLACES.get(workplace)
        or ("remote" if item.get("isRemote") else work_mode_from_text(location)),
    )
