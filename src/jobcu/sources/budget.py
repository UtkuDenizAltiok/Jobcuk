"""Keeps job sources within their free usage limits.

Some sources allow only a certain number of requests per day or month (Adzuna: 250 a
day and 2,500 a month). Jobcu counts every request and stops a source before a limit
is reached, and tells the user instead of failing.
"""

import calendar
import threading
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from jobcu import db


@dataclass(frozen=True)
class Limits:
    per_search: int | None = None
    per_day: int | None = None
    per_month: int | None = None


# How far back Jobcu looks to see how many searches a person runs a day.
HABIT_DAYS = 14


def share_of_month(
    source: str,
    limits: Limits,
    *,
    searches_per_day: float | None = None,
    fewest: int = 25,
    most: int = 60,
    now=lambda: datetime.now(UTC),
) -> Limits:
    """Spreads what is left of a monthly free allowance over the rest of the month.

    A fixed number of requests per search wastes the allowance on quiet days and runs out
    early on busy ones. This shares what is left over the days still to come, at the number of
    searches this person really runs a day (the last two weeks: one a day for the owner, more
    for others), and never allows more than is left today.
    """
    if limits.per_month is None:
        return limits
    today = now()
    used_today, used_this_month = _used(source, today)
    days_left = calendar.monthrange(today.year, today.month)[1] - today.day + 1
    left_this_month = max(0, limits.per_month - used_this_month)
    if searches_per_day is None:
        searches_per_day = searches_a_day(today)
    per_search = int(left_this_month / days_left / searches_per_day)
    per_search = max(fewest, min(most, per_search))
    if limits.per_day is not None:
        per_search = min(per_search, max(0, limits.per_day - used_today))
    return replace(limits, per_search=per_search)


def searches_a_day(now: datetime) -> float:
    """How many searches a day this person ran in the last two weeks: at least one."""
    since = (now - timedelta(days=HABIT_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
    with db.connect() as conn:
        searches = conn.execute(
            "SELECT COUNT(*) FROM searches WHERE started_at >= ?", (since,)
        ).fetchone()[0]
    return max(1.0, searches / HABIT_DAYS)


def _used(source: str, now: datetime) -> tuple[int, int]:
    day = now.strftime("%Y-%m-%d")
    with db.connect() as conn:
        today = conn.execute(
            "SELECT COALESCE(SUM(count), 0) FROM source_requests WHERE source = ? AND day = ?",
            (source, day),
        ).fetchone()[0]
        month = conn.execute(
            "SELECT COALESCE(SUM(count), 0) FROM source_requests "
            "WHERE source = ? AND substr(day, 1, 7) = ?",
            (source, day[:7]),
        ).fetchone()[0]
    return today, month


class BudgetExhausted(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RequestBudget:
    def __init__(self, source: str, name: str, limits: Limits, now=lambda: datetime.now(UTC)):
        self.source = source
        self.name = name
        self.limits = limits
        self.used_this_search = 0
        self._now = now
        self._lock = threading.Lock()

    def spend(self, count: int = 1) -> None:
        """Count one request (or `count` billed items), or raise BudgetExhausted if a limit
        would be passed."""
        with self._lock:
            today = self._now().strftime("%Y-%m-%d")
            month = today[:7]
            with db.connect() as conn:
                used_today = conn.execute(
                    "SELECT COALESCE(SUM(count), 0) FROM source_requests "
                    "WHERE source = ? AND day = ?",
                    (self.source, today),
                ).fetchone()[0]
                used_month = conn.execute(
                    "SELECT COALESCE(SUM(count), 0) FROM source_requests "
                    "WHERE source = ? AND substr(day, 1, 7) = ?",
                    (self.source, month),
                ).fetchone()[0]
                if self.limits.per_search is not None and (
                    self.used_this_search + count > self.limits.per_search
                ):
                    raise BudgetExhausted(
                        f"{self.name}: used this search's share of its free requests."
                    )
                if self.limits.per_day is not None and used_today + count > self.limits.per_day:
                    raise BudgetExhausted(
                        f"{self.name}: today's free requests are used up. It will work again "
                        "tomorrow."
                    )
                if self.limits.per_month is not None and (
                    used_month + count > self.limits.per_month
                ):
                    raise BudgetExhausted(
                        f"{self.name}: this month's free requests are used up. It will work again "
                        "next month."
                    )
                conn.execute(
                    "INSERT INTO source_requests (day, source, count) VALUES (?, ?, ?) "
                    "ON CONFLICT (day, source) DO UPDATE SET count = count + excluded.count",
                    (today, self.source, count),
                )
            self.used_this_search += count
