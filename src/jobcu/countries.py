"""The countries Jobcu searches, and the languages job ads there are commonly written in.
English is always searched in addition.

The owner's decision (2026-09-17): the 20 European countries with the highest GDP per person
(IMF World Economic Outlook, 2025, current US dollars), leaving out tiny states with under 100,000
people (Liechtenstein, San Marino, Andorra, Monaco, Vatican City), which have very few jobs.
Ireland, the United Kingdom and Germany are worked on first.
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
        Country("CY", "Cyprus", ("el",)),
        Country("CZ", "Czechia", ("cs",)),
        Country("DK", "Denmark", ("da",)),
        Country("FI", "Finland", ("fi", "sv")),
        Country("FR", "France", ("fr",)),
        Country("DE", "Germany", ("de",)),
        Country("IS", "Iceland", ("is",)),
        Country("IE", "Ireland", ()),
        Country("IT", "Italy", ("it",)),
        Country("LU", "Luxembourg", ("fr", "de")),
        Country("MT", "Malta", ()),
        Country("NL", "Netherlands", ("nl",)),
        Country("NO", "Norway", ("no",)),
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
    "fi": "Finnish",
    "fr": "French",
    "is": "Icelandic",
    "it": "Italian",
    "nl": "Dutch",
    "no": "Norwegian",
    "sl": "Slovenian",
    "sv": "Swedish",
}


def languages_for(country_codes: list[str]) -> list[str]:
    """English first, then the other job-ad languages of these countries, without repeats."""
    languages = ["en"]
    for code in country_codes:
        for language in COUNTRIES[code].ad_languages:
            if language not in languages:
                languages.append(language)
    return languages
