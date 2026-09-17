from datetime import UTC, datetime, timedelta

from jobcu.freshness import day_at_utc, days_back, freshness, parse_iso, window_start

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


def test_exact_times_are_compared_directly():
    start = window_start(NOW, 6)
    assert freshness(NOW - timedelta(hours=5), "exact", start) == "fresh"
    assert freshness(NOW - timedelta(hours=7), "exact", start) == "too_old"


def test_a_day_is_too_old_only_when_the_whole_day_is_before_the_window():
    start = window_start(NOW, 24)
    two_days_ago = day_at_utc((NOW - timedelta(days=2)).date())
    yesterday = day_at_utc((NOW - timedelta(days=1)).date())
    assert freshness(two_days_ago, "day", start) == "too_old"
    assert freshness(yesterday, "day", start) == "fresh"
    # "Today" can't be proven older than 6 hours, so it isn't hidden.
    assert freshness(day_at_utc(NOW.date()), "day", window_start(NOW, 6)) == "fresh"


def test_unknown_dates_stay_unknown():
    assert freshness(None, "unknown", window_start(NOW, 24)) == "unknown"


def test_whole_days_cover_the_window():
    assert [days_back(h) for h in (6, 24, 72, 168)] == [1, 1, 3, 7]


def test_iso_dates_are_read_with_time_zones():
    assert parse_iso("2026-09-17T13:32:59Z") == datetime(2026, 9, 17, 13, 32, 59, tzinfo=UTC)
    assert parse_iso("2026-09-17T13:32:59").tzinfo is not None
    assert parse_iso("not a date") is None
