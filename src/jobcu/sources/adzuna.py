"""Adzuna: an official job search API with a free key (Application ID + Application Key)."""

import logging

import httpx

from jobcu.keystore import KeyStore
from jobcu.sources.http import KeyCheck, client

log = logging.getLogger(__name__)

API = "https://api.adzuna.com/v1/api/jobs"
KEY_APP_ID = "adzuna_app_id"
KEY_APP_KEY = "adzuna_app_key"


def check_keys(keys: KeyStore) -> KeyCheck:
    app_id, app_key = keys.get(KEY_APP_ID), keys.get(KEY_APP_KEY)
    if not app_id or not app_key:
        return KeyCheck(False, "Please save both the Application ID and the Application Key.")
    try:
        with client() as http:
            response = http.get(
                f"{API}/gb/search/1",
                params={"app_id": app_id, "app_key": app_key, "results_per_page": 1},
            )
    except httpx.HTTPError as exc:
        # The request address contains the key, so only the error type is logged.
        log.warning("Adzuna key check failed: %s", type(exc).__name__)
        return KeyCheck(False, "Jobcu couldn't reach Adzuna. Check your internet connection.")
    if response.status_code == 200:
        return KeyCheck(True, "Adzuna keys work.")
    if response.status_code in (401, 403):
        return KeyCheck(
            False,
            "Adzuna didn't accept these keys. Check that the Application ID and Application Key "
            "are copied completely and not swapped.",
        )
    if response.status_code == 429:
        return KeyCheck(False, "Adzuna says its usage limit is reached. Try again later.")
    return KeyCheck(
        False, f"Adzuna answered with an unexpected problem (code {response.status_code})."
    )
