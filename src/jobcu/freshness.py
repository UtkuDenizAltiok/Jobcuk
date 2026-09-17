"""Posting dates and the "Posted within" filter (HANDOVER section 7).

- A job **proven** older than the chosen window is hidden.
- A job whose date can't be found is shown in a separate "Posting date unknown" section.
- Some sources give only the day. Such a job is hidden only if the whole day lies before
  the window; otherwise it's shown with its day ("posted today").
- When several copies of a job exist, the **earliest** date counts, which catches old
  jobs that were reposted.
"""

import math
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

Freshness = Literal["fresh", "too_old", "unknown"]

# Sources give days in European local time; this margin covers every time zone Jobcu
# searches, so a job is never hidden because of a time-zone difference.
DAY_MARGIN = timedelta(hours=3)


def window_start(started_at: datetime, hours: int) -> datetime:
    return started_at - timedelta(hours=hours)


def days_back(hours: int) -> int:
    """For sources that filter by whole days: enough days to cover the window."""
    return max(1, math.ceil(hours / 24))


def earliest_possible(posted_at: datetime | None, precision: str) -> datetime | None:
    if posted_at is None or precision == "unknown":
        return None
    if precision == "day":
        return datetime.combine(posted_at.date(), time(0), tzinfo=UTC) - DAY_MARGIN
    return posted_at


def latest_possible(posted_at: datetime | None, precision: str) -> datetime | None:
    if posted_at is None or precision == "unknown":
        return None
    if precision == "day":
        return datetime.combine(posted_at.date() + timedelta(days=1), time(0), tzinfo=UTC) + (
            DAY_MARGIN
        )
    return posted_at


def freshness(posted_at: datetime | None, precision: str, start: datetime) -> Freshness:
    latest = latest_possible(posted_at, precision)
    if latest is None:
        return "unknown"
    return "fresh" if latest >= start else "too_old"


def day_at_utc(day: date) -> datetime:
    """A day-precision date stored as midday UTC, so it stays the same day everywhere."""
    return datetime.combine(day, time(12), tzinfo=UTC)


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)
