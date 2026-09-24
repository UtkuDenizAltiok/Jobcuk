"""Records the tokens every AI request uses, for the usage meter and monthly limits."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jobcu import db
from jobcu.ai.base import Usage
from jobcu.settings import ModelPrice


@dataclass
class ModelUsage:
    provider: str
    model: str
    usage: Usage


class UsageLog:
    def __init__(self, folder: Path | None = None) -> None:
        self.folder = folder

    def record(
        self, *, step: str, provider: str, model: str, usage: Usage, search_id: int | None = None
    ) -> None:
        with db.connect(self.folder) as conn:
            conn.execute(
                """INSERT INTO ai_usage (search_id, step, provider, model, input_tokens,
                   output_tokens, cached_input_tokens, reasoning_tokens, web_searches)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (search_id, step, provider, model, usage.input_tokens, usage.output_tokens,
                 usage.cached_input_tokens, usage.reasoning_tokens, usage.web_searches),
            )

    def this_month(self, now: datetime | None = None) -> list[ModelUsage]:
        now = now or datetime.now(UTC)
        month_start = now.strftime("%Y-%m-01T00:00:00")
        return self._by_model("created_at >= ?", (month_start,))

    def for_search(self, search_id: int) -> dict[str, Usage]:
        """Usage per step of one search, for "Search details"."""
        with db.connect(self.folder) as conn:
            rows = conn.execute(
                """SELECT step, SUM(input_tokens), SUM(output_tokens), SUM(cached_input_tokens),
                   SUM(reasoning_tokens), SUM(web_searches)
                   FROM ai_usage WHERE search_id = ? GROUP BY step""",
                (search_id,),
            ).fetchall()
        return {row[0]: Usage(*row[1:]) for row in rows}

    def for_search_by_model(self, search_id: int, step: str | None = None) -> list[ModelUsage]:
        """One search's usage per model (of one step, if given), so its cost can be estimated."""
        if step is not None:
            return self._by_model("search_id = ? AND step = ?", (search_id, step))
        return self._by_model("search_id = ?", (search_id,))

    def _by_model(self, where: str, params: tuple) -> list[ModelUsage]:
        with db.connect(self.folder) as conn:
            rows = conn.execute(
                f"""SELECT provider, model, SUM(input_tokens), SUM(output_tokens),
                    SUM(cached_input_tokens), SUM(reasoning_tokens), SUM(web_searches)
                    FROM ai_usage WHERE {where} GROUP BY provider, model""",
                params,
            ).fetchall()
        return [ModelUsage(row[0], row[1], Usage(*row[2:])) for row in rows]


def total_tokens(usages: list[ModelUsage]) -> int:
    return sum(u.usage.input_tokens + u.usage.output_tokens for u in usages)


def estimate_cost(usages: list[ModelUsage], prices: list[ModelPrice]) -> tuple[float, bool]:
    """Estimated cost from the user's price table.

    Returns the cost of the models with a known price, and whether every model used
    had a price (if not, the real cost is higher than the estimate).
    """
    table = {(p.provider, p.model): p for p in prices}
    cost = 0.0
    complete = True
    for item in usages:
        price = table.get((item.provider, item.model))
        if price is None:
            complete = complete and (item.usage.input_tokens + item.usage.output_tokens == 0)
            continue
        cost += item.usage.input_tokens / 1e6 * price.input_per_million
        cost += item.usage.output_tokens / 1e6 * price.output_per_million
    return cost, complete
