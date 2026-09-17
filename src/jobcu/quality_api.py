"""Internal API behind the Score check screen (HANDOVER section 13)."""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jobcu import quality

router = APIRouter(prefix="/api")


@router.get("/quality")
def get_quality() -> dict:
    return {
        "progress": quality.progress(),
        "blockers": [{"id": key, "label": label} for key, label in quality.BLOCKERS.items()],
        "ads": [asdict(ad) for ad in quality.all_ads()],
    }


class Rating(BaseModel):
    rating: str | None = None
    blockers: list[str] = []
    note: str = Field(default="", max_length=500)


@router.put("/quality/{ad_id}")
def put_rating(ad_id: int, rating: Rating) -> dict:
    try:
        ad = quality.rate(ad_id, rating.rating, rating.blockers, rating.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown job.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ad": asdict(ad), "progress": quality.progress()}
