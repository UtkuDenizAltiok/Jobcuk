"""Internal API behind the Settings screen: AI provider, model, keys, key checks, what has been
used this month, the limits, the price table and which job sources are on."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jobcu import db, travel
from jobcu.ai.base import AIError
from jobcu.ai.client import check_setup
from jobcu.ai.providers import PROVIDERS
from jobcu.ai.usage import ModelUsage, UsageLog, estimate_cost, total_tokens
from jobcu.keystore import KeyStore, KeyStoreError, mask
from jobcu.settings import LimitSettings, ModelPrice, ProviderId, load_settings, save_settings
from jobcu.sources import adzuna, all_sources, reed
from jobcu.sources.http import PoliteClient

router = APIRouter(prefix="/api")

JOB_SITE_KEYS = {
    adzuna.KEY_APP_ID: "Adzuna Application ID",
    adzuna.KEY_APP_KEY: "Adzuna Application Key",
    reed.KEY_API_KEY: "Reed API key",
}
TRAVEL_KEYS = {travel.KEY_NAME: "Google Maps API key"}
ALLOWED_KEYS = ({info.key_name for info in PROVIDERS.values()} | set(JOB_SITE_KEYS)
                | set(TRAVEL_KEYS))


def _key_status(keys: KeyStore, name: str) -> dict:
    try:
        value = keys.get(name)
    except KeyStoreError:
        value = None
    return {"name": name, "saved": bool(value), "hint": mask(value) if value else None}


@router.get("/settings")
def get_settings() -> dict:
    settings = load_settings()
    keys = KeyStore()
    return {
        "ai": settings.ai.model_dump(),
        "providers": [
            {
                "id": info.id,
                "name": info.name,
                "key_page": info.key_page,
                "needs_base_url": info.needs_base_url,
                "key_optional": info.key_optional,
                "key": _key_status(keys, info.key_name),
            }
            for info in PROVIDERS.values()
        ],
        "job_site_keys": [
            {**_key_status(keys, name), "label": label} for name, label in JOB_SITE_KEYS.items()
        ],
        "travel_keys": [
            {**_key_status(keys, name), "label": label} for name, label in TRAVEL_KEYS.items()
        ],
    }


class AIChoice(BaseModel):
    provider: ProviderId | None
    model: str = ""
    reasoning_model: str = ""
    base_url: str = ""


@router.put("/settings/ai")
def put_ai_settings(choice: AIChoice) -> dict:
    settings = load_settings()
    settings.ai.provider = choice.provider
    settings.ai.model = choice.model.strip()
    settings.ai.reasoning_model = choice.reasoning_model.strip()
    settings.ai.base_url = choice.base_url.strip()
    save_settings(settings)
    return get_settings()


class KeyValue(BaseModel):
    value: str


def _allowed(name: str) -> str:
    if name not in ALLOWED_KEYS:
        raise HTTPException(status_code=404, detail="Unknown key.")
    return name


@router.put("/keys/{name}")
def put_key(name: str, body: KeyValue) -> dict:
    keys = KeyStore()
    try:
        keys.set(_allowed(name), body.value)
    except KeyStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _key_status(keys, name)


@router.delete("/keys/{name}")
def delete_key(name: str) -> dict:
    keys = KeyStore()
    keys.delete(_allowed(name))
    return _key_status(keys, name)


class ModelListRequest(BaseModel):
    provider: ProviderId
    base_url: str = ""


@router.post("/ai/models")
def list_models(request: ModelListRequest) -> dict:
    info = PROVIDERS[request.provider]
    key = KeyStore().get(info.key_name) or ""
    if not key and not info.key_optional:
        return {"models": [], "error": "Please save your key for this provider first."}
    if info.needs_base_url and not request.base_url.strip():
        return {"models": [], "error": "Please enter the provider's address first."}
    try:
        models = info.adapter(key, base_url=request.base_url.strip(), timeout=30).list_models()
    except AIError as exc:
        return {"models": [], "error": exc.message}
    return {"models": models, "error": None}


@router.post("/ai/check")
def check_ai() -> dict:
    result = check_setup(load_settings(), KeyStore(), usage_log=UsageLog())
    return {"ok": result.ok, "message": result.message}


@router.post("/job-sites/{site}/check")
def check_job_site(site: str) -> dict:
    checks = {"adzuna": adzuna.check_keys, "reed": reed.check_keys}
    if site not in checks:
        raise HTTPException(status_code=404, detail="Unknown job site.")
    result = checks[site](KeyStore())
    return {"ok": result.ok, "message": result.message}


@router.post("/travel/check")
def check_travel() -> dict:
    http = PoliteClient()
    try:
        ok, message = travel.check_key(KeyStore(), http)
    finally:
        http.close()
    return {"ok": ok, "message": message}


class Limits(BaseModel):
    scoring_cap: int
    monthly_token_limit: int | None = None
    monthly_cost_limit: float | None = None
    maps_monthly_routes: int | None = None
    maps_monthly_places: int | None = None


@router.put("/settings/limits")
def put_limits(limits: Limits) -> dict:
    settings = load_settings()
    settings.limits = LimitSettings(
        scoring_cap=limits.scoring_cap,
        web_search_cap=settings.limits.web_search_cap,
        monthly_token_limit=limits.monthly_token_limit,
        monthly_cost_limit=limits.monthly_cost_limit,
        maps_monthly_routes=(limits.maps_monthly_routes if limits.maps_monthly_routes is not None
                             else settings.limits.maps_monthly_routes),
        maps_monthly_places=(limits.maps_monthly_places if limits.maps_monthly_places is not None
                             else settings.limits.maps_monthly_places),
    )
    save_settings(settings)
    return get_usage()


class Prices(BaseModel):
    prices: list[ModelPrice]


@router.put("/settings/prices")
def put_prices(body: Prices) -> dict:
    settings = load_settings()
    settings.prices = body.prices
    save_settings(settings)
    return get_usage()


class SourceChoice(BaseModel):
    disabled: list[str]


@router.put("/settings/sources")
def put_sources(choice: SourceChoice) -> dict:
    known = {source.id for source in all_sources()}
    settings = load_settings()
    settings.sources_disabled = sorted(set(choice.disabled) & known)
    save_settings(settings)
    return get_usage()


def _source_requests(now: datetime) -> tuple[dict[str, int], dict[str, int]]:
    day = now.strftime("%Y-%m-%d")
    with db.connect() as conn:
        today = conn.execute(
            "SELECT source, SUM(count) AS used FROM source_requests WHERE day = ? GROUP BY source",
            (day,),
        ).fetchall()
        month = conn.execute(
            "SELECT source, SUM(count) AS used FROM source_requests "
            "WHERE substr(day, 1, 7) = ? GROUP BY source",
            (day[:7],),
        ).fetchall()
    return ({row["source"]: row["used"] for row in today},
            {row["source"]: row["used"] for row in month})


def _money(usages: list[ModelUsage], prices: list[ModelPrice]) -> dict:
    cost, complete = estimate_cost(usages, prices)
    currencies = {price.currency for price in prices} or {"USD"}
    return {"tokens": total_tokens(usages), "cost": round(cost, 2), "cost_is_complete": complete,
            "currency": currencies.pop() if len(currencies) == 1 else ""}


@router.get("/usage")
def get_usage(now: datetime | None = None) -> dict:
    """What has been used this month and in the last search, and the state of every source."""
    now = now or datetime.now(UTC)
    settings = load_settings()
    log = UsageLog()
    this_month = log.this_month(now)
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id, started_at FROM searches ORDER BY id DESC LIMIT 1"
        ).fetchone()
    last_search = None
    if row is not None:
        used = log.for_search_by_model(row["id"])
        last_search = {"started_at": row["started_at"], **_money(used, settings.prices)}
    today, month = _source_requests(now)
    return {
        "this_month": {
            **_money(this_month, settings.prices),
            "by_model": [
                {"provider": item.provider, "model": item.model,
                 **_money([item], settings.prices)}
                for item in sorted(this_month, key=lambda i: (i.provider, i.model))
            ],
        },
        "last_search": last_search,
        "travel": {
            "routes_this_month": month.get("google_maps_routes", 0),
            "places_this_month": month.get("google_maps_places", 0),
        },
        "limits": settings.limits.model_dump(),
        "prices": [price.model_dump() for price in settings.prices],
        "sources": [
            {
                "id": source.id,
                "name": source.name,
                "enabled": source.id not in settings.sources_disabled,
                "requests_today": today.get(source.id, 0),
                "requests_this_month": month.get(source.id, 0),
                "needs_key": bool(source.unavailable_reason(KeyStore())),
            }
            for source in all_sources()
        ],
    }
