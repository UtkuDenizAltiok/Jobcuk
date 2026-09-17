"""Reed: an official UK job search API with a free key."""

import logging

import httpx

from jobcu.keystore import KeyStore
from jobcu.sources.http import KeyCheck, client

log = logging.getLogger(__name__)

API = "https://www.reed.co.uk/api/1.0"
KEY_API_KEY = "reed_api_key"


def check_keys(keys: KeyStore) -> KeyCheck:
    api_key = keys.get(KEY_API_KEY)
    if not api_key:
        return KeyCheck(False, "Please save the Reed key first.")
    try:
        with client() as http:
            # Reed expects the key as the user name, with an empty password.
            response = http.get(
                f"{API}/search", params={"keywords": "engineer", "resultsToTake": 1},
                auth=(api_key, ""),
            )
    except httpx.HTTPError as exc:
        log.warning("Reed key check failed: %s", type(exc).__name__)
        return KeyCheck(False, "Jobcu couldn't reach Reed. Check your internet connection.")
    if response.status_code == 200:
        return KeyCheck(True, "Reed key works.")
    if response.status_code in (401, 403):
        return KeyCheck(False, "Reed didn't accept this key. Check that you copied the whole key.")
    if response.status_code == 429:
        return KeyCheck(False, "Reed says its usage limit is reached. Try again later.")
    return KeyCheck(
        False, f"Reed answered with an unexpected problem (code {response.status_code})."
    )
