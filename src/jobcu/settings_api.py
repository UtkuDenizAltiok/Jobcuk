"""Internal API behind the Settings screen: AI provider, model, keys and key checks."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jobcu.ai.base import AIError
from jobcu.ai.client import check_setup
from jobcu.ai.providers import PROVIDERS
from jobcu.ai.usage import UsageLog
from jobcu.keystore import KeyStore, KeyStoreError, mask
from jobcu.settings import ProviderId, load_settings, save_settings
from jobcu.sources import adzuna, reed

router = APIRouter(prefix="/api")

JOB_SITE_KEYS = {
    adzuna.KEY_APP_ID: "Adzuna Application ID",
    adzuna.KEY_APP_KEY: "Adzuna Application Key",
    reed.KEY_API_KEY: "Reed API key",
}
ALLOWED_KEYS = {info.key_name for info in PROVIDERS.values()} | set(JOB_SITE_KEYS)


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
