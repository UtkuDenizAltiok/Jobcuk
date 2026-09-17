import pytest

from jobcu.placenames import OTHER, countries_in, is_europe_wide


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Dublin, Ireland", {"IE"}),
        ("Swords, Co. Dublin", {"IE"}),
        ("London, England", {"GB"}),
        ("Belfast, Northern Ireland", {"GB"}),
        ("Cambridge, UK", {"GB"}),
        ("York, United Kingdom", {"GB"}),
        ("München", {"DE"}),
        ("Oberpfaffenhofen, Bavaria", {"DE"}),
        ("Berlin, DE", {"DE"}),
        ("Ireland, Limerick", {"IE"}),
        ("Zürich or Geneva", {"CH"}),
        ("Dublin, Ireland; London, England", {"IE", "GB"}),
        # The same town names elsewhere in the world.
        ("Dublin, CA", {OTHER}),
        ("Dublin, Ohio", {OTHER}),
        ("Cambridge, MA", {OTHER}),
        ("New York", {OTHER}),
        ("USA, Remote", {OTHER}),
        ("Remote - US", {OTHER}),
        ("Sydney, Australia", {OTHER}),
        # Nothing to tell.
        ("Remote", set()),
        ("", set()),
        (None, set()),
    ],
)
def test_countries_in_location_text(text, expected):
    assert countries_in(text) == expected


def test_europe_wide_locations():
    assert is_europe_wide("Remote - EMEA")
    assert is_europe_wide("Anywhere in Europe")
    assert not is_europe_wide("Remote")
    assert not is_europe_wide("Dublin, Ireland")
