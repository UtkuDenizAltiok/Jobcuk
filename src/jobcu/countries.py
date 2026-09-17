"""The countries Jobcu searches, and the languages job ads there are commonly written in.
English is always searched in addition.

The owner's decision (2026-09-17): 30 European countries. These are the 20 with the highest GDP
per person (IMF World Economic Outlook 2025), leaving out tiny states such as Liechtenstein and
Monaco, plus Poland, Portugal, Romania, Greece, Hungary, Croatia, Slovakia, Estonia, Latvia and
Lithuania. Ireland, the United Kingdom and Germany are worked on first.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    code: str  # ISO 3166-1 alpha-2 ("GB" for the United Kingdom)
    name: str
    ad_languages: tuple[str, ...]  # besides English
    people: int = 0  # roughly how many people live there


# People per country, rounded (Eurostat and national statistics offices, 2024/2025). Used only
# for conditions about a town's size, such as "a city with at least 0.3% of the country's people".
COUNTRIES: dict[str, Country] = {
    country.code: country
    for country in (
        Country("AT", "Austria", ("de",), 9_160_000),
        Country("BE", "Belgium", ("nl", "fr"), 11_830_000),
        Country("HR", "Croatia", ("hr",), 3_860_000),
        Country("CY", "Cyprus", ("el",), 940_000),
        Country("CZ", "Czechia", ("cs",), 10_900_000),
        Country("DK", "Denmark", ("da",), 5_970_000),
        Country("EE", "Estonia", ("et",), 1_370_000),
        Country("FI", "Finland", ("fi", "sv"), 5_600_000),
        Country("FR", "France", ("fr",), 68_400_000),
        Country("DE", "Germany", ("de",), 83_500_000),
        Country("GR", "Greece", ("el",), 10_400_000),
        Country("HU", "Hungary", ("hu",), 9_580_000),
        Country("IS", "Iceland", ("is",), 390_000),
        Country("IE", "Ireland", (), 5_310_000),
        Country("IT", "Italy", ("it",), 58_990_000),
        Country("LV", "Latvia", ("lv",), 1_870_000),
        Country("LT", "Lithuania", ("lt",), 2_890_000),
        Country("LU", "Luxembourg", ("fr", "de"), 670_000),
        Country("MT", "Malta", (), 560_000),
        Country("NL", "Netherlands", ("nl",), 17_940_000),
        Country("NO", "Norway", ("no",), 5_550_000),
        Country("PL", "Poland", ("pl",), 36_620_000),
        Country("PT", "Portugal", ("pt",), 10_640_000),
        Country("RO", "Romania", ("ro",), 19_060_000),
        Country("SK", "Slovakia", ("sk",), 5_430_000),
        Country("SI", "Slovenia", ("sl",), 2_120_000),
        Country("ES", "Spain", ("es",), 48_590_000),
        Country("SE", "Sweden", ("sv",), 10_550_000),
        Country("CH", "Switzerland", ("de", "fr", "it"), 8_960_000),
        Country("GB", "United Kingdom", (), 68_350_000),
    )
}

LANGUAGE_NAMES: dict[str, str] = {
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "et": "Estonian",
    "fi": "Finnish",
    "fr": "French",
    "hr": "Croatian",
    "hu": "Hungarian",
    "is": "Icelandic",
    "it": "Italian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sv": "Swedish",
}


def languages_for(country_codes: list[str], places=()) -> list[str]:
    """The languages search words are written in: English first, then only the languages needed
    for where the person wants to work. When places are named in a country with several
    languages, only those places' languages are used (Zürich → German, not French or Italian)."""
    languages = ["en"]
    for code in country_codes:
        country_languages = COUNTRIES[code].ad_languages
        named = [
            language
            for place in places
            if place.country == code
            for language in getattr(place, "languages", [])
            if language in country_languages
        ]
        for language in named or country_languages:
            if language not in languages:
                languages.append(language)
    return languages
