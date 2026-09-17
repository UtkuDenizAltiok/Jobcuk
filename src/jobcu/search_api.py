"""Internal API for starting a search and following its progress."""

from fastapi import APIRouter, HTTPException

from jobcu import search
from jobcu.settings import SearchForm, load_settings, save_settings

router = APIRouter(prefix="/api/search")


@router.get("/form")
def get_form() -> dict:
    return load_settings().search_form.model_dump()


@router.post("")
def start_search(form: SearchForm) -> dict:
    if not form.job_types:
        raise HTTPException(status_code=400, detail="Please tick at least one job type.")
    settings = load_settings()
    settings.search_form = form
    save_settings(settings)
    try:
        run = search.manager.start(form)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail="A search is already running.") from exc
    return run.snapshot()


@router.get("/current")
def current_search() -> dict:
    run = search.manager.current
    return {"search": run.snapshot() if run else None}


@router.post("/{search_id}/stop")
def stop_search(search_id: int) -> dict:
    return {"stopping": search.manager.stop(search_id)}
