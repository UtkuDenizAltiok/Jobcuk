"""The countries Jobcu searches: every country that lies fully or mostly in Europe (the owner's
decision, 2026-09-17), and the languages job ads there are commonly written in. English is always
searched in addition. Countries mostly in Asia (Turkey, Russia, Kazakhstan, Georgia, Armenia,
Azerbaijan) are not included; Cyprus is, as an EU member."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    code: str  # ISO 3166-1 alpha-2 ("GB" for the United Kingdom)
    name: str
    ad_languages: tuple[str, ...]  # besides English


COUNTRIES: dict[str, Country] = {
    country.code: country
    for country in (
        Country("AL", "Albania", ("sq",)),
        Country("AD", "Andorra", ("ca", "es", "fr")),
        Country("AT", "Austria", ("de",)),
        Country("BY", "Belarus", ("ru", "be")),
        Country("BE", "Belgium", ("nl", "fr")),
        Country("BA", "Bosnia and Herzegovina", ("bs", "hr", "sr")),
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
        Country("XK", "Kosovo", ("sq", "sr")),
        Country("LV", "Latvia", ("lv",)),
        Country("LI", "Liechtenstein", ("de",)),
        Country("LT", "Lithuania", ("lt",)),
        Country("LU", "Luxembourg", ("fr", "de")),
        Country("MT", "Malta", ()),
        Country("MD", "Moldova", ("ro", "ru")),
        Country("MC", "Monaco", ("fr",)),
        Country("ME", "Montenegro", ("sr",)),
        Country("NL", "Netherlands", ("nl",)),
        Country("MK", "North Macedonia", ("mk", "sq")),
        Country("NO", "Norway", ("no",)),
        Country("PL", "Poland", ("pl",)),
        Country("PT", "Portugal", ("pt",)),
        Country("RO", "Romania", ("ro",)),
        Country("SM", "San Marino", ("it",)),
        Country("RS", "Serbia", ("sr",)),
        Country("SK", "Slovakia", ("sk",)),
        Country("SI", "Slovenia", ("sl",)),
        Country("ES", "Spain", ("es",)),
        Country("SE", "Sweden", ("sv",)),
        Country("CH", "Switzerland", ("de", "fr", "it")),
        Country("UA", "Ukraine", ("uk",)),
        Country("GB", "United Kingdom", ()),
        Country("VA", "Vatican City", ("it",)),
    )
}

LANGUAGE_NAMES: dict[str, str] = {
    "be": "Belarusian",
    "bg": "Bulgarian",
    "bs": "Bosnian",
    "ca": "Catalan",
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
    "mk": "Macedonian",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sq": "Albanian",
    "sr": "Serbian",
    "sv": "Swedish",
    "uk": "Ukrainian",
}


def languages_for(country_codes: list[str]) -> list[str]:
    """English first, then the other job-ad languages of these countries, without repeats."""
    languages = ["en"]
    for code in country_codes:
        for language in COUNTRIES[code].ad_languages:
            if language not in languages:
                languages.append(language)
    return languages
