"""prospective.ch career sites: a Swiss career system used by the federal administration,
cantons, university hospitals, universities and companies. Checked 2026-09-24.

`GET https://ohws.prospective.ch/public/v1/medium/{board}/jobs?lang=de&offset=N&limit=100`
returns an employer's jobs with the ad's parts (tasks, requirements, benefits), the place, the
workload in percent and the exact publication time; no key, and ohws.prospective.ch's
robots.txt allows everything. The board is the number of the employer's career centre
(`/public/v1/careercenter/{board}/`).
"""

import re
from collections.abc import Iterator

from jobcu.freshness import parse_iso
from jobcu.placenames import OTHER, countries_in
from jobcu.sources.base import FoundJob, SourceContext
from jobcu.sources.careers import CareerSystemSource, Employer, job_types_from_text
from jobcu.text import html_to_text, tidy

API = "https://ohws.prospective.ch/public/v1/medium/{board}/jobs"
PAGE_SIZE = 100
MAX_PAGES = 20  # the biggest employers have a few hundred jobs

_AD_PARTS = ("sza_role", "sza_tasks", "sza_requirements", "sza_benefits", "sza_company_profil")


class ProspectiveSource(CareerSystemSource):
    id = "prospective"
    name = "Company career sites (prospective.ch)"
    system = "prospective"

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None,
                  terms=None) -> Iterator[FoundJob]:
        for page in range(MAX_PAGES):
            data = self.get_json(API.format(board=employer.board), ctx, params={
                "lang": "de", "offset": page * PAGE_SIZE, "limit": PAGE_SIZE})
            jobs = data.get("jobs") or []
            for item in jobs:
                job = to_found_job(item, employer)
                if job is not None:
                    yield job
            if len(jobs) < PAGE_SIZE or (page + 1) * PAGE_SIZE >= int(data.get("total") or 0):
                return


def _workload(szas: dict) -> tuple[int | None, int | None]:
    def percent(name: str) -> int | None:
        try:
            return int(float(szas.get(name)))
        except (TypeError, ValueError):
            return None
    return percent("sza_pensum.min"), percent("sza_pensum.max")


def _job_types(title: str, szas: dict) -> list[str]:
    """From the title's words (Praktikum, befristet) and the workload: in Switzerland 100 % is
    full time, and a range like 80-100 % suits both full- and part-time seekers."""
    from_words = job_types_from_text(title)
    low, high = _workload(szas)
    part_time = (low is not None and low < 90) or (high is not None and high < 90)
    if "internship_or_working_student" in from_words or "freelance_or_contract" in from_words:
        types = [t for t in from_words if t != "part_time"]
    elif high is not None and high >= 90:
        types = ["fixed_term" if "fixed_term" in from_words else "full_time_permanent"]
    else:
        types = [t for t in from_words if t == "fixed_term"]
    return [*types, "part_time"] if part_time or "part_time" in from_words else types


def _place(szas: dict) -> tuple[str | None, str | None]:
    """ "Bussnang, Schweiz" and its country. A job without a place is in Switzerland: the
    system serves Swiss employers, and those hiring abroad name the country."""
    city = tidy(szas.get("sza_location.city") or "")
    country_name = tidy(szas.get("sza_location.country") or "")
    if country_name and country_name.casefold() in city.casefold():
        country_name = ""  # "Santiago de Chile, Chile" already names it
    location = ", ".join(part for part in (city, country_name) if part) or None
    country_name = country_name or tidy(szas.get("sza_location.country") or "")
    if not location:
        return None, "CH"
    codes = countries_in(country_name or location) - {OTHER}
    return location, (next(iter(codes)) if len(codes) == 1 else None)


def to_found_job(item: dict, employer: Employer) -> FoundJob | None:
    title = html_to_text(item.get("title") or "")
    link = (item.get("links") or {}).get("directlink") or ""
    if not title or not link:
        return None
    szas = item.get("szas") or {}
    location, country = _place(szas)
    posted = parse_iso(item.get("start_date"))
    parts = [html_to_text(szas.get(part)) for part in _AD_PARTS]
    low, high = _workload(szas)
    workload = (f"Workload: {low} %" if low == high else f"Workload: {low}-{high} %"
                ) if low is not None and high is not None else ""
    return FoundJob(
        source="prospective",
        source_job_id=f"{employer.board}/{item.get('id') or re.sub(r'.*/', '', link)}",
        url=link,
        title=title,
        company=employer.name,
        location_text=location,
        country=country,
        posted_at=posted,
        date_precision="exact" if posted else "unknown",
        description=tidy("\n\n".join(part for part in [workload, *parts] if part)),
        description_is_complete=True,
        job_types=_job_types(title, szas),
    )
