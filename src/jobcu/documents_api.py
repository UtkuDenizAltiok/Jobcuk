"""Internal API for uploading the CV and cover letter, and previewing what Jobcu understood."""

import logging
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from jobcu import documents
from jobcu.ai.base import AIError
from jobcu.ai.client import AIClient
from jobcu.ai.usage import UsageLog
from jobcu.documents import DocumentError
from jobcu.keystore import KeyStore
from jobcu.profile import read_profile_reusing
from jobcu.settings import load_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

KINDS = ("cv", "cover_letter")


def _kind(kind: str) -> documents.DocumentKind:
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail="Unknown document.")
    return kind  # type: ignore[return-value]


def _info(kind: documents.DocumentKind) -> dict | None:
    info = documents.get_info(kind)
    return asdict(info) if info else None


@router.get("/documents")
def list_documents() -> dict:
    return {
        "documents": {kind: _info(kind) for kind in KINDS},
        "accepted": {kind: list(documents.ALLOWED_EXTENSIONS[kind]) for kind in KINDS},
    }


@router.post("/documents/{kind}")
def upload_document(kind: str, file: Annotated[UploadFile, File()]) -> dict:
    checked = _kind(kind)
    content = file.file.read(documents.MAX_UPLOAD_BYTES + 1)
    try:
        info = documents.save_upload(checked, file.filename or "", content)
    except DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return asdict(info)


@router.delete("/documents/{kind}")
def delete_document(kind: str) -> dict:
    documents.delete(_kind(kind))
    return {"deleted": True}


class PreviewRequest(BaseModel):
    about_you: str = Field(default="", max_length=500)


@router.post("/profile/preview")
def preview_profile(body: PreviewRequest | None = None) -> dict:
    """Read the documents (and the person's note, as typed) now and show the profile."""
    try:
        cv_text = documents.read_text("cv")
        cover_letter_text = documents.read_text("cover_letter")
        client = AIClient(load_settings(), KeyStore(), usage_log=UsageLog())
        profile, _reused = read_profile_reusing(client, cv_text, cover_letter_text,
                                                body.about_you if body else "")
    except DocumentError as exc:
        return {"profile": None, "error": str(exc)}
    except AIError as exc:
        log.warning("Profile preview failed: %s", exc.detail or exc.message)
        return {"profile": None, "error": exc.message}
    return {"profile": profile.model_dump(), "error": None}
