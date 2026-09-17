"""Shared, polite HTTP settings for talking to job sources."""

import httpx

from jobcu import __version__

USER_AGENT = f"Jobcu/{__version__} (personal job search app)"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def client(**kwargs) -> httpx.Client:
    # trust_env=False: never send requests through proxies set elsewhere on the computer.
    return httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True,
        trust_env=False, **kwargs,
    )


class KeyCheck:
    """The result of testing a job site key, in plain words."""

    def __init__(self, ok: bool, message: str) -> None:
        self.ok = ok
        self.message = message
