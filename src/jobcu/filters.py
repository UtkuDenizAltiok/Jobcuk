"""The free rules filter (HANDOVER section 11, step 1): objective facts only, no AI.

A job is left out only when a fact proves it doesn't fit:
- it was marked Not interested before
- it's proven older than "Posted within"
- the source states a job type the user didn't tick
- the source states it's fully remote and remote jobs are excluded
- the source states a country outside the countries searched
- a location condition the AI checked says this place doesn't fit (for example a town that is
  too small, or one the person asked to avoid). A job whose place can't be recognised is kept
  and shown as "not checked" on its card.

Every left-out job is counted with its reason, for "Search details".
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from jobcu.dedupe import JobGroup
from jobcu.freshness import freshness, window_start
from jobcu.jobstore import JobState
from jobcu.location import fits

REASONS = {
    "dismissed": "Marked Not interested before",
    "location_condition": "The place doesn't fit a condition you wrote",
    "too_old": "Older than your \"Posted within\" choice",
    "job_type": "A job type you didn't tick",
    "remote": "Fully remote (you excluded remote jobs)",
    "country": "In a country you didn't search",
}


@dataclass
class FilterOutcome:
    kept: list[int] = field(default_factory=list)  # indexes into the groups
    left_out: Counter = field(default_factory=Counter)


def apply_rules(
    groups: list[JobGroup],
    remembered_states: list[JobState | None],
    *,
    started_at: datetime,
    posted_within_hours: int,
    job_types: list[str],
    exclude_remote: bool,
    countries: list[str],
    conditions: list | None = None,
) -> FilterOutcome:
    outcome = FilterOutcome()
    start = window_start(started_at, posted_within_hours)
    wanted_types = set(job_types)
    for index, group in enumerate(groups):
        reason = _reason(group, remembered_states[index], start, wanted_types, exclude_remote,
                         set(countries), conditions or [])
        if reason:
            outcome.left_out[reason] += 1
        else:
            outcome.kept.append(index)
    return outcome


def _reason(group, state, start, wanted_types, exclude_remote, countries, conditions
            ) -> str | None:
    if state is not None and state.dismissed:
        return "dismissed"
    if freshness(group.posted_at, group.date_precision, start) == "too_old":
        return "too_old"
    stated_types = [c.job_types for c in group.copies if c.job_types]
    # Left out only if every copy that states a type says it's something not ticked.
    if stated_types and all(not (set(types) & wanted_types) for types in stated_types):
        return "job_type"
    if exclude_remote and any(c.work_mode == "remote" for c in group.copies):
        return "remote"
    stated_countries = {c.country for c in group.copies if c.country}
    if stated_countries and not (stated_countries & countries):
        return "country"
    if any(condition_fit(condition, group) == "no" for condition in conditions):
        return "location_condition"
    return None


def condition_fit(condition, group: JobGroup) -> str:
    """"yes", "no" or "unknown" for a job and one of the conditions the person wrote."""
    country = next((c.country for c in group.copies if c.country), None)
    answers = {fits(condition, country, copy.location_text) for copy in group.copies}
    if "yes" in answers:
        return "yes"
    return "no" if "no" in answers else "unknown"
