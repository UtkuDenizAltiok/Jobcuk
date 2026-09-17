"""What Jobcu remembers about jobs between searches (HANDOVER section 12).

Only this is remembered: which jobs were shown before (for the "New" badge), and which
the user marked Saved, Applied or Not interested. A job is recognised again through any
of its copies, so if one copy was marked Not interested, every copy stays hidden.
"""

import json
from dataclasses import dataclass

from jobcu import db
from jobcu.dedupe import JobGroup, normal_city, normal_company, normal_title


@dataclass
class JobState:
    saved: bool = False
    applied: bool = False
    dismissed: bool = False


def identity_keys(group: JobGroup) -> list[str]:
    keys = []
    for copy in group.copies:
        keys.append(f"copy:{copy.source}:{copy.source_job_id}")
        company, title = normal_company(copy.company), normal_title(copy.title)
        if company and title:
            keys.append(f"job:{company}|{title}|{normal_city(copy.location_text)}")
    return list(dict.fromkeys(keys))


def find_job_ids(groups: list[JobGroup]) -> list[int | None]:
    """The remembered job for each group, or None if this job was never seen."""
    with db.connect() as conn:
        found: list[int | None] = []
        for group in groups:
            keys = identity_keys(group)
            marks = ",".join("?" * len(keys))
            row = conn.execute(
                f"SELECT job_id FROM job_keys WHERE key IN ({marks}) ORDER BY job_id LIMIT 1", keys
            ).fetchone()
            found.append(row[0] if row else None)
    return found


def states(job_ids: list[int]) -> dict[int, JobState]:
    if not job_ids:
        return {}
    with db.connect() as conn:
        marks = ",".join("?" * len(job_ids))
        rows = conn.execute(
            f"SELECT job_id, saved, applied, dismissed FROM job_states WHERE job_id IN ({marks})",
            job_ids,
        ).fetchall()
    return {row[0]: JobState(bool(row[1]), bool(row[2]), bool(row[3])) for row in rows}


def remember(groups: list[JobGroup], search_id: int) -> tuple[list[int], list[bool]]:
    """Record the jobs shown in a search. Returns each job's id and whether it's new."""
    ids: list[int] = []
    new: list[bool] = []
    with db.connect() as conn:
        for group in groups:
            keys = identity_keys(group)
            marks = ",".join("?" * len(keys))
            row = conn.execute(
                f"SELECT job_id FROM job_keys WHERE key IN ({marks}) ORDER BY job_id LIMIT 1", keys
            ).fetchone()
            if row:
                job_id = row[0]
                earlier = conn.execute(
                    "SELECT first_seen_search_id FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()[0]
                new.append(earlier == search_id)
            else:
                job_id = conn.execute(
                    "INSERT INTO jobs (first_seen_search_id, title, company) VALUES (?, ?, ?)",
                    (search_id, group.main.title, group.main.company),
                ).lastrowid
                new.append(True)
            conn.executemany(
                "INSERT OR IGNORE INTO job_keys (key, job_id) VALUES (?, ?)",
                [(key, job_id) for key in keys],
            )
            ids.append(job_id)
    return ids, new


def set_state(job_id: int, **changes: bool) -> JobState:
    allowed = {"saved", "applied", "dismissed"}
    changes = {k: bool(v) for k, v in changes.items() if k in allowed}
    with db.connect() as conn:
        if conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is None:
            raise KeyError(job_id)
        conn.execute("INSERT OR IGNORE INTO job_states (job_id) VALUES (?)", (job_id,))
        for name, value in changes.items():
            conn.execute(
                f"UPDATE job_states SET {name} = ?, "
                "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE job_id = ?",
                (int(value), job_id),
            )
    return states([job_id])[job_id]


def save_results(search_id: int, result_json: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO search_results (search_id, result_json) VALUES (?, ?)",
            (search_id, result_json),
        )


def latest_results() -> tuple[int, str] | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT search_id, result_json FROM search_results ORDER BY search_id DESC LIMIT 1"
        ).fetchone()
    return (row[0], row[1]) if row else None


def save_cards(cards: list[dict]) -> None:
    with db.connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO job_cards (job_id, card_json) VALUES (?, ?)",
            [(card["job_id"], json.dumps(card)) for card in cards],
        )


def marked_cards(kind: str) -> list[dict]:
    """Cards of every job marked Saved or Applied, newest change first."""
    if kind not in ("saved", "applied"):
        return []
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT c.card_json, s.saved, s.applied, s.dismissed FROM job_states s "
            f"JOIN job_cards c ON c.job_id = s.job_id WHERE s.{kind} = 1 "
            "ORDER BY s.updated_at DESC"
        ).fetchall()
    cards = []
    for row in rows:
        card = json.loads(row[0])
        card["state"] = {"saved": bool(row[1]), "applied": bool(row[2]), "dismissed": bool(row[3])}
        cards.append(card)
    return cards
