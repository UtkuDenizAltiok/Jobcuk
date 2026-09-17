"""The score check (HANDOVER section 13): does Jobcu's scoring match the person's own judgement?

Every search quietly keeps a few of its real job ads, spread across the whole score range, and a
few of the titles the quick relevance check left out. On the **Score check** screen the person
says what they think of each one: a good fit, okay, or poor, and whether a title was really
unrelated. The answers stay in the data folder, never in the repository.

`tools/score_check.py` then measures Jobcu's scores against those answers, which is how the
scoring prompt, the quick check, the batch size and the reasoning effort get tuned.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from jobcu import db

RATINGS = ("good", "okay", "poor")
TITLE_RATINGS = ("unrelated", "worth_a_look")
BLOCKERS = {
    "field": "Wrong field of work",
    "seniority": "Level or years don't fit",
    "language": "Language requirement",
    "location": "Place doesn't fit",
    "job_type": "Job type I don't want",
    "permit": "Work permit or clearance",
    "company": "Company I don't want",
}
# How many ads the set holds, and how many one search may add.
WANTED = {"scored": 40, "title_only": 40}
PER_SEARCH = {"scored": 8, "title_only": 8}
# Scored ads are kept across the whole range, so the check isn't only about the top jobs.
BANDS = ((0, 39), (40, 59), (60, 74), (75, 100))


@dataclass
class Ad:
    id: int
    kind: str
    title: str
    company: str | None
    location: str | None
    url: str
    score: int | None
    text: str
    rating: str | None = None
    blockers: list[str] = field(default_factory=list)
    note: str = ""
    rated_by: str | None = None

    @classmethod
    def from_row(cls, row) -> "Ad":
        return cls(
            id=row["id"], kind=row["kind"], title=row["title"], company=row["company"],
            location=row["location"], url=row["url"], score=row["score"], text=row["text"],
            rating=row["rating"], blockers=json.loads(row["blockers_json"] or "[]"),
            note=row["note"] or "", rated_by=row["rated_by"],
        )


def add(kind: str, items: list[dict]) -> int:
    """Adds job ads or titles to the set, ignoring ones already there. Returns how many were new."""
    if kind not in WANTED:
        raise ValueError(f"Unknown kind: {kind}")
    added = 0
    with db.connect() as conn:
        have = conn.execute(
            "SELECT COUNT(*) FROM quality_ads WHERE kind = ?", (kind,)
        ).fetchone()[0]
        room = max(0, WANTED[kind] - have)
        for item in items[:room]:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO quality_ads
                   (kind, source, source_job_id, title, company, location, url, score, text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kind, item.get("source", ""), item.get("source_job_id", ""), item["title"],
                 item.get("company"), item.get("location"), item.get("url", ""),
                 item.get("score"), item.get("text", "")),
            )
            added += cursor.rowcount or 0
    return added


def spread_by_score(ads: list[dict], most: int) -> list[dict]:
    """Picks ads from every part of the score range, so the check covers good and poor ones."""
    chosen: list[dict] = []
    for low, high in BANDS:
        in_band = [ad for ad in ads if ad.get("score") is not None and low <= ad["score"] <= high]
        chosen.extend(in_band[: max(1, most // len(BANDS))])
    for ad in ads:  # fill up with whatever is left if some bands were empty
        if len(chosen) >= most:
            break
        if ad not in chosen:
            chosen.append(ad)
    return chosen[:most]


def collect_from_search(scored_ads: list[dict], left_out_titles: list[dict]) -> dict[str, int]:
    """Called at the end of a search: keeps a few of its jobs for the score check."""
    return {
        "scored": add("scored", spread_by_score(scored_ads, PER_SEARCH["scored"])),
        "title_only": add("title_only", left_out_titles[: PER_SEARCH["title_only"]]),
    }


def all_ads() -> list[Ad]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM quality_ads ORDER BY kind, rating IS NOT NULL, id"
        ).fetchall()
    return [Ad.from_row(row) for row in rows]


def rate(ad_id: int, rating: str | None, blockers: list[str], note: str, by: str = "owner") -> Ad:
    kinds = {"scored": RATINGS, "title_only": TITLE_RATINGS}
    with db.connect() as conn:
        row = conn.execute("SELECT kind FROM quality_ads WHERE id = ?", (ad_id,)).fetchone()
        if row is None:
            raise KeyError(ad_id)
        if rating is not None and rating not in kinds[row["kind"]]:
            raise ValueError(f"Unknown rating: {rating}")
        conn.execute(
            """UPDATE quality_ads SET rating = ?, blockers_json = ?, note = ?, rated_by = ?,
               rated_at = ? WHERE id = ?""",
            (rating, json.dumps([b for b in blockers if b in BLOCKERS]), note.strip()[:500],
             by if rating else None,
             datetime.now(UTC).isoformat(timespec="seconds") if rating else None, ad_id),
        )
        return Ad.from_row(conn.execute(
            "SELECT * FROM quality_ads WHERE id = ?", (ad_id,)
        ).fetchone())


def progress() -> dict:
    ads = all_ads()
    return {
        kind: {
            "wanted": WANTED[kind],
            "collected": sum(1 for ad in ads if ad.kind == kind),
            "rated": sum(1 for ad in ads if ad.kind == kind and ad.rating),
        }
        for kind in WANTED
    }
