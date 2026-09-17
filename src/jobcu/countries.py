"""The countries Jobcu searches (EU, UK, Switzerland, Norway, Iceland) and the languages
job ads there are commonly written in. English is always searched in addition."""

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
        Country("BG", "Bulgaria", ("bg",)),
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
    "bg": "Bulgarian",
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


def languages_for(country_codes: list[str]) -> list[str]:
    """English first, then the other job-ad languages of these countries, without repeats."""
    languages = ["en"]
    for code in country_codes:
        for language in COUNTRIES[code].ad_languages:
            if language not in languages:
                languages.append(language)
    return languages
