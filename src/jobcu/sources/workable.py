"""Workable career sites, through Workable's public job widget API (made for showing a
company's jobs on other sites; no key). Checked 2026-09-17: robots.txt allows everything.

`GET /api/v1/widget/accounts/{board}` lists every job with its title, place, country and
publication day; the full ad comes from `GET /api/v2/accounts/{board}/jobs/{shortcode}` for
jobs that are still in the running.
"""

import dataclasses
from collections.abc import Iterator
from datetime import date

from jobcu.freshness import day_at_utc
from jobcu.sources.base import FoundJob, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted
from jobcu.sources.careers import CareerSystemSource, Employer, job_types_from_text
from jobcu.text import html_to_text, tidy

SITE = "https://apply.workable.com/api"


class WorkableSource(CareerSystemSource):
    id = "workable"
    name = "Company career sites (Workable)"
    system = "workable"

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None,
                  terms=None) -> Iterator[FoundJob]:
        data = self.get_json(f"{SITE}/v1/widget/accounts/{employer.board}", ctx)
        for item in data.get("jobs") or []:
            yield to_found_job(item, employer)

    def load_details(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        board, _, shortcode = job.source_job_id.partition("/")
        try:
            item = self.get_json(f"{SITE}/v2/accounts/{board}/jobs/{shortcode}", ctx)
        except (SourceError, BudgetExhausted, ValueError):
            return job
        parts = [html_to_text(item.get(key)) for key in ("description", "requirements", "benefits")]
        description = tidy("\n\n".join(p for p in parts if p))
        if not description:
            return job
        return dataclasses.replace(job, description=description, description_is_complete=True)


def to_found_job(item: dict, employer: Employer) -> FoundJob:
    places = item.get("locations") or [{"city": item.get("city"), "country": item.get("country"),
                                        "countryCode": None}]
    location = "; ".join(
        ", ".join(part for part in (place.get("city"), place.get("country")) if part)
        for place in places
    ) or None
    codes = {place.get("countryCode") for place in places if place.get("countryCode")}
    try:
        posted = day_at_utc(date.fromisoformat(item.get("published_on") or ""))
    except ValueError:
        posted = None
    return FoundJob(
        source="workable",
        source_job_id=f"{employer.board}/{item.get('shortcode')}",
        url=item.get("url") or item.get("shortlink") or "",
        title=(item.get("title") or "").strip(),
        company=employer.name,
        location_text=location,
        country=next(iter(codes)).upper() if len(codes) == 1 else None,
        posted_at=posted,
        date_precision="day" if posted else "unknown",
        job_types=job_types_from_text(item.get("employment_type")),
        work_mode="remote" if item.get("telecommuting") else None,
    )
