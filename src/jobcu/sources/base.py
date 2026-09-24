"""What every job source has in common.

Each source is an isolated module that turns its own format into `FoundJob`s. A source
that fails only marks itself as failed in the report; the search carries on
(HANDOVER section 9.1).
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.settings import JobType
from jobcu.sources.http import PoliteClient

DatePrecision = Literal["exact", "day", "unknown"]
WorkMode = Literal["remote", "hybrid", "on_site"]
SourceKind = Literal["employer", "linkedin", "job_board", "aggregator"]
SourceStatus = Literal["ok", "partial", "failed", "unavailable", "skipped"]


@dataclass
class FoundJob:
    """One job ad as one source shows it. Several of these may describe the same real job."""

    source: str
    source_job_id: str
    url: str
    title: str
    company: str | None = None
    location_text: str | None = None
    country: str | None = None  # ISO code, when the source says it
    latitude: float | None = None
    longitude: float | None = None
    posted_at: datetime | None = None  # timezone-aware
    date_precision: DatePrecision = "unknown"
    description: str = ""
    description_is_complete: bool = False
    job_types: list[JobType] = field(default_factory=list)  # as stated by the source
    work_mode: WorkMode | None = None  # as stated by the source
    employer_url: str | None = None  # the employer's own page or career system, if known
    salary_text: str | None = None
    via: str | None = None  # e.g. "Found through Reed" for career-system jobs
    closes_at: datetime | None = None  # when applications close, if the source says (aware)
    # A career site's title that none of the search words match: the person's AI looks at the
    # title before the job is dropped (relevance.screen_titles).
    title_unmatched: bool = False


@dataclass
class JobQuery:
    """What every source is asked for in one search."""

    countries: list[str]
    places: list[Place]
    terms: list[SearchTerm]
    posted_within_hours: int
    started_at: datetime


@dataclass
class SourceReport:
    source: str
    name: str
    status: SourceStatus = "ok"
    jobs_found: int = 0
    requests: int = 0
    message: str = ""


@dataclass
class SourceContext:
    http: PoliteClient
    keys: KeyStore
    report: SourceReport
    should_stop: Callable[[], bool]
    note: Callable[[str], None]


class JobSource(ABC):
    id: str
    name: str
    kind: SourceKind
    countries: frozenset[str] | None = None  # None means every supported country

    def covers(self, query: JobQuery) -> bool:
        return self.countries is None or bool(self.countries & set(query.countries))

    def unavailable_reason(self, keys: KeyStore) -> str | None:
        """Why this source can't run now (e.g. a missing key), or None."""
        return None

    @abstractmethod
    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        """Yield the jobs this source finds (short versions are fine). Raise SourceError."""

    def load_details(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        """Fetch the full ad for a job that is still in the running. Default: nothing to add."""
        return job


class SourceError(Exception):
    """A plain-language problem with one source. Other sources are not affected."""
