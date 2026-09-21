"""Polite HTTP for job sources (HANDOVER section 9.1).

- a clear User-Agent naming Jobcu
- a minimum pause between requests to the same site
- waits and retries on "too many requests" and temporary server errors, respecting Retry-After
- answers are remembered during one search, so the same page is never fetched twice
- never logs request addresses, because some contain keys
"""

import logging
import random
import threading
import time
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

from jobcu import __version__

log = logging.getLogger(__name__)

USER_AGENT = f"Jobcu/{__version__} (personal job search app)"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DEFAULT_MIN_INTERVAL = 1.0  # seconds between requests to the same site
MAX_RETRIES = 3
MAX_WAIT = 120.0


def client(**kwargs) -> httpx.Client:
    # trust_env=False: never send requests through proxies set elsewhere on the computer.
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True,
        trust_env=False,
        **kwargs,
    )


# Pauses between requests for sites with known limits (Adzuna allows 25 a minute).
SITE_INTERVALS = {
    "api.adzuna.com": 2.6,
    "www.reed.co.uk": 0.5,
    "rest.arbeitsagentur.de": 0.7,
    "jobsireland.ie": 2.0,
    "www.jobs.ac.uk": 1.5,
    "euraxess.ec.europa.eu": 4.0,
    # Company career systems' public job lists (Lever's robots.txt asks for 1 s).
    "boards-api.greenhouse.io": 0.5,
    "api.lever.co": 1.0,
    "api.eu.lever.co": 1.0,
    "api.ashbyhq.com": 1.0,
    "apply.workable.com": 1.0,
    "www.arbeitnow.com": 1.0,
    "www.arbeitnow.co.uk": 1.0,
    # Sweden's open job data (CC0, no stated limit): pages are big, so a short pause is enough.
    "jobsearch.api.jobtechdev.se": 0.5,
    # Adzuna's job pages are read at a relaxed, human-like pace.
    **{f"www.adzuna.{ending}": 3.0
       for ending in ("de", "co.uk", "at", "be", "ch", "es", "fr", "it", "nl", "pl")},
}


class KeyCheck:
    """The result of testing a job site key, in plain words."""

    def __init__(self, ok: bool, message: str) -> None:
        self.ok = ok
        self.message = message


class Blocked(Exception):
    """The site refused Jobcu (e.g. bot protection). Jobcu never tries to get around this."""


class PoliteClient:
    """One per search. Safe to share between sources running in parallel."""

    def __init__(
        self,
        min_intervals: dict[str, float] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
            follow_redirects=True,
            trust_env=False,
            transport=transport,
        )
        self._min_intervals = SITE_INTERVALS if min_intervals is None else min_intervals
        self._last_request: dict[str, float] = {}
        self._host_locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()
        self._cache: dict[tuple, httpx.Response] = {}
        self._sleep = sleep
        self.request_count: dict[str, int] = {}

    def close(self) -> None:
        self._client.close()

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def request(self, method: str, url: str, *, cache: bool = True, **kwargs) -> httpx.Response:
        key = (method, url, repr(sorted((kwargs.get("params") or {}).items())),
               repr(kwargs.get("json")))
        if cache and key in self._cache:
            return self._cache[key]
        host = urlsplit(url).hostname or ""
        for attempt in range(MAX_RETRIES + 1):
            self._wait_turn(host)
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                if attempt == MAX_RETRIES:
                    raise
                log.info("Network problem with %s (%s), retrying", host, type(exc).__name__)
                self._sleep(min(2 ** attempt * 2, MAX_WAIT) + random.uniform(0, 1))
                continue
            finally:
                with self._lock:
                    self.request_count[host] = self.request_count.get(host, 0) + 1
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == MAX_RETRIES:
                    break
                wait = _retry_after(response) or min(2 ** attempt * 5, MAX_WAIT)
                log.info("%s answered %s, waiting %.0fs", host, response.status_code, wait)
                self._sleep(min(wait, MAX_WAIT))
                continue
            break
        if response.status_code in (401, 403, 429) and _looks_like_bot_protection(response):
            raise Blocked(host)
        if cache and response.status_code == 200:
            self._cache[key] = response
        return response

    def _wait_turn(self, host: str) -> None:
        with self._lock:
            host_lock = self._host_locks.setdefault(host, threading.Lock())
        with host_lock:
            interval = self._min_intervals.get(host, DEFAULT_MIN_INTERVAL)
            elapsed = time.monotonic() - self._last_request.get(host, 0.0)
            if elapsed < interval:
                self._sleep(interval - elapsed)
            self._last_request[host] = time.monotonic()


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _looks_like_bot_protection(response: httpx.Response) -> bool:
    text = response.text[:2000].lower()
    return any(
        marker in text
        for marker in ("captcha", "cf-chl", "cloudflare", "are you a robot", "access denied")
    )
