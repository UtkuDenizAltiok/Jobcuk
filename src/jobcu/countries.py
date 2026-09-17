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


COUNTRIES: dict[str, Country] = {
    country.code: country
    for country in (
        Country("AT", "Austria", ("de",)),
        Country("BE", "Belgium", ("nl", "fr")),
        Country("HR", "Croatia", ("hr",)),
        Country("CY", "Cyprus", ("el",)),
        Country("CZ", "Czechia", ("cs",)),
        Country("DK", "Denmark", ("da",)),
        Country("EE", "Estonia", ("et",)),
        Country("FI", "Finland", ("fi", "sv")),
        Country("FR", "France", ("fr",)),
        Country("DE", "Germany", ("de",)),
        Country("GR", "Greece", ("el",)),
        Country("HU", "Hungary", ("hu",)),
        Country("IS", "Iceland", ("is",)),
        Country("IE", "Ireland", ()),
        Country("IT", "Italy", ("it",)),
        Country("LV", "Latvia", ("lv",)),
        Country("LT", "Lithuania", ("lt",)),
        Country("LU", "Luxembourg", ("fr", "de")),
        Country("MT", "Malta", ()),
        Country("NL", "Netherlands", ("nl",)),
        Country("NO", "Norway", ("no",)),
        Country("PL", "Poland", ("pl",)),
        Country("PT", "Portugal", ("pt",)),
        Country("RO", "Romania", ("ro",)),
        Country("SK", "Slovakia", ("sk",)),
        Country("SI", "Slovenia", ("sl",)),
        Country("ES", "Spain", ("es",)),
        Country("SE", "Sweden", ("sv",)),
        Country("CH", "Switzerland", ("de", "fr", "it")),
        Country("GB", "United Kingdom", ()),
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
