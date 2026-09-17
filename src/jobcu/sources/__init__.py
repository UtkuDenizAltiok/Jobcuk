"""Job sources: one isolated module per source. A failing source never breaks a search."""

from jobcu.sources.adzuna import AdzunaSource
from jobcu.sources.base import JobSource
from jobcu.sources.bundesagentur import BundesagenturSource
from jobcu.sources.reed import ReedSource


def all_sources() -> list[JobSource]:
    """Fresh source objects for one search, in the order they're shown."""
    return [AdzunaSource(), BundesagenturSource(), ReedSource()]
