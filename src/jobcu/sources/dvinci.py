"""d.vinci career sites, through d.vinci's Job Publication API ("since ATS version 2022.11 the
job publication api is always public"; documented for job aggregators among others). Checked
2026-09-24.

`GET https://{board}.dvinci-hr.com/jobPublication/list.json` returns every published job with
its ad in parts (introduction, tasks, profile, offer), its places with coordinates and country
code, the working time and the contract period. d.vinci is common with German hospitals,
councils and mid-sized employers.

The publication's own start date is often empty, so a job's date is when its opening was
created: an "always open" post from years ago is then honestly old.
"""

from collections.abc import Iterator

from jobcu.freshness import parse_iso
from jobcu.sources.base import FoundJob, SourceContext
from jobcu.sources.careers import CareerSystemSource, Employer
from jobcu.text import html_to_text, tidy

API = "https://{board}.dvinci-hr.com/jobPublication/list.json"
_AD_PARTS = ("introduction", "tasks", "profile", "weOffer", "closingText")


class DvinciSource(CareerSystemSource):
    id = "dvinci"
    name = "Company career sites (d.vinci)"
    system = "dvinci"
    parallel = 4  # every employer has its own address

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None,
                  terms=None) -> Iterator[FoundJob]:
        data = self.get_json(API.format(board=employer.board), ctx)
        for item in data if isinstance(data, list) else []:
            job = to_found_job(item, employer)
            if job is not None:
                yield job


def _job_types(opening: dict) -> list[str]:
    period = ((opening.get("contractPeriod") or {}).get("internalName") or "").upper()
    times = {(t.get("internalName") or "").upper() for t in opening.get("workingTimes") or []}
    types = []
    if period == "UNLIMITED" and ("FULL_TIME" in times or not times):
        types.append("full_time_permanent")
    elif period in ("LIMITED", "FIXED_TERM", "TEMPORARY"):
        types.append("fixed_term")
    if times & {"PART_TIME", "MINI_JOB", "MARGINAL_EMPLOYMENT"}:
        types.append("part_time")
    kind = (opening.get("type") or "").upper()
    if kind in ("INTERNSHIP", "APPRENTICESHIP", "TRAINEE", "STUDENT"):
        types = ["internship_or_working_student"]
    return types


def to_found_job(item: dict, employer: Employer) -> FoundJob | None:
    opening = item.get("jobOpening") or {}
    title = tidy(item.get("position") or opening.get("name") or "")
    url = item.get("jobPublicationURL") or ""
    if not title or not url:
        return None
    places = opening.get("locations") or []
    towns = [tidy(place.get("name") or (place.get("address") or {}).get("city") or "")
             for place in places if isinstance(place, dict)]
    codes = {((place.get("country") or {}).get("isoA2") or "").upper()
             for place in places if isinstance(place, dict)} - {""}
    first = places[0] if places and isinstance(places[0], dict) else {}
    posted = parse_iso(item.get("startDate")) or parse_iso(opening.get("createdDate"))
    parts = [html_to_text(item.get(part)) for part in _AD_PARTS]
    return FoundJob(
        source="dvinci",
        source_job_id=f"{employer.board}/{item.get('id')}",
        url=url,
        title=title,
        company=employer.name,
        location_text=", ".join(dict.fromkeys(t for t in towns if t)) or None,
        country=next(iter(codes)) if len(codes) == 1 else None,
        latitude=first.get("latitude") if len(places) == 1 else None,
        longitude=first.get("longitude") if len(places) == 1 else None,
        posted_at=posted,
        date_precision="exact" if posted else "unknown",
        description=tidy("\n\n".join(p for p in parts if p)),
        description_is_complete=any(parts),
        job_types=_job_types(opening),
    )
