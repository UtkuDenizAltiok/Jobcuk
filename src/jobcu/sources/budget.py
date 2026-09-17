"""Keeps job sources within their free usage limits.

Some sources allow only a certain number of requests per day or month (Adzuna: 250 a
day and 2,500 a month). Jobcu counts every request and stops a source before a limit
is reached, and tells the user instead of failing.
"""

import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from jobcu import db


@dataclass(frozen=True)
class Limits:
    per_search: int | None = None
    per_day: int | None = None
    per_month: int | None = None


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

    def spend(self) -> None:
        """Count one request, or raise BudgetExhausted if a limit would be passed."""
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
                    self.used_this_search >= self.limits.per_search
                ):
                    raise BudgetExhausted(
                        f"{self.name}: used this search's share of its free requests."
                    )
                if self.limits.per_day is not None and used_today >= self.limits.per_day:
                    raise BudgetExhausted(
                        f"{self.name}: today's free requests are used up. It will work again "
                        "tomorrow."
                    )
                if self.limits.per_month is not None and used_month >= self.limits.per_month:
                    raise BudgetExhausted(
                        f"{self.name}: this month's free requests are used up. It will work again "
                        "next month."
                    )
                conn.execute(
                    "INSERT INTO source_requests (day, source, count) VALUES (?, ?, 1) "
                    "ON CONFLICT (day, source) DO UPDATE SET count = count + 1",
                    (today, self.source),
                )
            self.used_this_search += 1
