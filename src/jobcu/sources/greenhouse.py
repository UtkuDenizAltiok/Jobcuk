"""Greenhouse career sites, through Greenhouse's public Job Board API (documented for building
career pages; no key). Checked 2026-09-17: robots.txt allows everything except /embed/.

`GET /v1/boards/{board}/jobs` lists every job with its title, location text and first
publication time; the full ad comes from `GET /v1/boards/{board}/jobs/{id}` for jobs that are
still in the running.
"""

import dataclasses
import html
from collections.abc import Iterator

from jobcu.freshness import parse_iso
from jobcu.sources.base import FoundJob, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted
from jobcu.sources.careers import CareerSystemSource, Employer, work_mode_from_text
from jobcu.text import html_to_text

API = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseSource(CareerSystemSource):
    id = "greenhouse"
    name = "Company career sites (Greenhouse)"
    system = "greenhouse"

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None
                  ) -> Iterator[FoundJob]:
        data = self.get_json(f"{API}/{employer.board}/jobs", ctx)
        for item in data.get("jobs") or []:
            yield to_found_job(item, employer)

    def load_details(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        board = job.source_job_id.split("/", 1)[0]
        job_id = job.source_job_id.split("/", 1)[-1]
        try:
            item = self.get_json(f"{API}/{board}/jobs/{job_id}", ctx)
        except (SourceError, BudgetExhausted, ValueError):
            return job
        description = html_to_text(html.unescape(item.get("content") or ""))
        if not description:
            return job
        offices = "; ".join(o.get("location") or o.get("name") or ""
                            for o in item.get("offices") or [])
        return dataclasses.replace(
            job,
            description=description,
            description_is_complete=True,
            work_mode=job.work_mode or work_mode_from_text(job.location_text or offices),
        )


def to_found_job(item: dict, employer: Employer) -> FoundJob:
    published = item.get("first_published") or item.get("updated_at")
    location = (item.get("location") or {}).get("name")
    return FoundJob(
        source="greenhouse",
        source_job_id=f"{employer.board}/{item.get('id')}",
        url=item.get("absolute_url") or "",
        title=(item.get("title") or "").strip(),
        company=employer.name,
        location_text=location,
        posted_at=parse_iso(published),
        date_precision="exact" if published else "unknown",
        work_mode=work_mode_from_text(location),
    )
