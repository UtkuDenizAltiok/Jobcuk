"""Reads the standard job data many job pages carry for search engines (schema.org JobPosting,
HANDOVER section 9.0 point 3). It gives the full ad text, the posting date, the job type and
whether the job is remote, in the same format on thousands of different sites.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from jobcu.freshness import parse_closing, parse_iso
from jobcu.text import html_to_text

_JSON_LD = re.compile(
    r"<script[^>]+type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)

_EMPLOYMENT_TYPES = {
    "FULL_TIME": ["full_time_permanent", "fixed_term"],
    "PART_TIME": ["part_time"],
    "CONTRACTOR": ["freelance_or_contract"],
    "TEMPORARY": ["fixed_term"],
    "INTERN": ["internship_or_working_student"],
}


@dataclass
class JobPosting:
    title: str = ""
    description: str = ""
    date_posted: datetime | None = None
    date_has_time: bool = False
    company: str | None = None
    location_text: str | None = None
    job_types: list[str] = field(default_factory=list)
    remote: bool = False
    valid_through: datetime | None = None  # when applications close


def find_job_posting(html: str) -> JobPosting | None:
    for block in _JSON_LD.findall(html or ""):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for item in _items(data):
            if _is_job_posting(item):
                return _read(item)
    return None


def _items(data) -> list[dict]:
    if isinstance(data, list):
        return [item for entry in data for item in _items(entry)]
    if isinstance(data, dict):
        return [data, *_items(data.get("@graph", []))]
    return []


def _is_job_posting(item: dict) -> bool:
    kind = item.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return "JobPosting" in kinds


def _read(item: dict) -> JobPosting:
    posted_text = str(item.get("datePosted") or "")
    types: list[str] = []
    raw_types = item.get("employmentType") or []
    for raw in raw_types if isinstance(raw_types, list) else [raw_types]:
        for mapped in _EMPLOYMENT_TYPES.get(str(raw).upper().replace("-", "_"), []):
            if mapped not in types:
                types.append(mapped)
    organisation = item.get("hiringOrganization")
    company = organisation.get("name") if isinstance(organisation, dict) else organisation
    return JobPosting(
        title=html_to_text(str(item.get("title") or "")),
        description=html_to_text(str(item.get("description") or "")),
        date_posted=parse_iso(posted_text) if posted_text else None,
        date_has_time="T" in posted_text,
        company=str(company) if company else None,
        location_text=_location(item.get("jobLocation")),
        job_types=types,
        remote=str(item.get("jobLocationType") or "").upper() == "TELECOMMUTE",
        valid_through=parse_closing(str(item.get("validThrough") or "")),
    )


def _location(value) -> str | None:
    places = value if isinstance(value, list) else [value]
    names = []
    for place in places:
        address = place.get("address") if isinstance(place, dict) else None
        if isinstance(address, dict):
            town = address.get("addressLocality") or address.get("addressRegion")
            if town and town not in names:
                names.append(str(town))
    return ", ".join(names) or None
