"""The countries Jobcu searches, and the languages job ads there are commonly written in.
English is always searched in addition.

The owner's decision (2026-09-17): 30 European countries. These are the 20 with the highest GDP
per person (IMF World Economic Outlook 2025), leaving out tiny states such as Liechtenstein and
Monaco, plus Poland, Portugal, Romania, Greece, Hungary, Croatia, Slovakia, Estonia, Latvia and
Lithuania. Ireland, the United Kingdom and Germany are worked on first.
"""

import unicodedata
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


# Other names of the same languages, as CVs and ads across Europe write them: the language's own
# name, and its name in the other main languages of the supported countries. A German CV says
# "Englisch", a French one "anglais", a Polish one "angielski"; all of them are English
# (`language_code`). Checked in scoring, where the person's languages meet the ad's.
LANGUAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "en": ("english", "englisch", "anglais", "engels", "inglés", "inglese", "angielski",
           "engelska", "inglês", "engelsk", "angol", "angličtina", "angleščina", "engleski",
           "anglų", "angļu", "inglise", "englanti", "αγγλικά", "engleză", "béarla"),
    "de": ("german", "deutsch", "allemand", "duits", "alemán", "tedesco", "niemiecki", "tyska",
           "alemão", "tysk", "német", "němčina", "nemčina", "nemščina", "njemački", "vokiečių",
           "vācu", "saksa", "γερμανικά", "germană"),
    "fr": ("french", "français", "französisch", "frans", "francés", "francese", "francuski",
           "franska", "francês", "fransk", "francia", "francouzština", "francúzština",
           "francoščina", "prancūzų", "franču", "prantsuse", "ranska", "γαλλικά", "franceză"),
    "nl": ("dutch", "nederlands", "niederländisch", "holländisch", "néerlandais", "neerlandés",
           "olandese", "niderlandzki", "holenderski", "nederländska", "holandês", "neerlandês",
           "nederlandsk", "hollandsk", "flemish", "vlaams", "flämisch", "flamand", "holland",
           "nizozemština", "holandčina", "nizozemščina", "nizozemski", "olandų", "holandiešu",
           "hollandi", "hollanti", "ολλανδικά", "neerlandeză"),
    "es": ("spanish", "español", "castellano", "spanisch", "espagnol", "spaans", "spagnolo",
           "hiszpański", "spanska", "espanhol", "spansk", "spanyol", "španělština",
           "španielčina", "španščina", "španjolski", "ispanų", "spāņu", "hispaania", "espanja",
           "ισπανικά", "spaniolă"),
    "it": ("italian", "italiano", "italienisch", "italien", "italiaans", "włoski", "italienska",
           "italiensk", "olasz", "italština", "taliančina", "italijanščina", "talijanski",
           "italų", "itāļu", "itaalia", "italia", "ιταλικά", "italiană"),
    "pl": ("polish", "polski", "polnisch", "polonais", "pools", "polaco", "polacco", "polska",
           "polonês", "polsk", "lengyel", "polština", "poľština", "poljščina", "poljski",
           "lenkų", "poļu", "poola", "puola", "πολωνικά", "poloneză"),
    "pt": ("portuguese", "português", "portugiesisch", "portugais", "portugees", "portugués",
           "portoghese", "portugalski", "portugisiska", "portugisisk", "portugál",
           "portugalština", "portugalčina", "portugalščina", "portugalų", "portugāļu",
           "portugali", "πορτογαλικά", "portugheză"),
    "sv": ("swedish", "svenska", "schwedisch", "suédois", "zweeds", "sueco", "svedese",
           "szwedzki", "svensk", "svéd", "švédština", "švédčina", "švedščina", "švedski",
           "švedų", "zviedru", "rootsi", "ruotsi", "σουηδικά", "suedeză"),
    "da": ("danish", "dansk", "dänisch", "danois", "deens", "danés", "danese", "duński",
           "danska", "dinamarquês", "dán", "dánština", "dánčina", "danščina", "danski", "danų",
           "dāņu", "taani", "tanska", "δανικά", "daneză"),
    "no": ("norwegian", "norsk", "bokmål", "nynorsk", "norwegisch", "norvégien", "noors",
           "noruego", "norvegese", "norweski", "norska", "norueguês", "norvég", "norština",
           "nórčina", "norveščina", "norveški", "norvegų", "norvēģu", "norra", "norja",
           "νορβηγικά", "norvegiană"),
    "fi": ("finnish", "suomi", "finnisch", "finnois", "fins", "finlandés", "finlandese",
           "fiński", "finska", "finlandês", "finsk", "finn", "finština", "fínčina", "finščina",
           "finski", "suomių", "somu", "soome", "φινλανδικά", "finlandeză"),
    "cs": ("czech", "čeština", "tschechisch", "tchèque", "tsjechisch", "checo", "ceco", "czeski",
           "tjeckiska", "tjekkisk", "tsjekkisk", "cseh", "češčina", "češki", "čekų", "čehu",
           "tšehhi", "tšekki", "τσεχικά", "cehă"),
    "sk": ("slovak", "slovenčina", "slowakisch", "slovaque", "slowaaks", "eslovaco", "slovacco",
           "słowacki", "slovakiska", "slovakisk", "szlovák", "slovenština", "slovaščina",
           "slovački", "slovakų", "slovāku", "slovaki", "slovakki", "σλοβακικά", "slovacă"),
    "sl": ("slovenian", "slovene", "slovenščina", "slowenisch", "slovène", "sloveens", "esloveno",
           "sloveno", "słoweński", "slovenska", "slovensk", "szlovén", "slovinština",
           "slovinčina", "slovenski", "slovėnų", "slovēņu", "sloveeni", "σλοβενικά", "slovenă"),
    "hr": ("croatian", "hrvatski", "kroatisch", "croate", "croata", "croato", "chorwacki",
           "kroatiska", "kroatisk", "horvát", "chorvatština", "chorvátčina", "hrvaščina",
           "kroatų", "horvātu", "horvaadi", "kroatia", "κροατικά", "croată"),
    "hu": ("hungarian", "magyar", "ungarisch", "hongrois", "hongaars", "húngaro", "ungherese",
           "węgierski", "ungerska", "ungarsk", "maďarština", "maďarčina", "madžarščina",
           "mađarski", "vengrų", "ungāru", "ungari", "unkari", "ουγγρικά", "maghiară"),
    "ro": ("romanian", "română", "rumänisch", "roumain", "roemeens", "rumano", "rumeno",
           "rumuński", "rumänska", "romeno", "rumænsk", "rumensk", "román", "rumunština",
           "rumunčina", "romunščina", "rumunjski", "rumunų", "rumāņu", "rumeenia", "romania",
           "ρουμανικά"),
    "el": ("greek", "ελληνικά", "griechisch", "grec", "grieks", "griego", "greco", "grecki",
           "grekiska", "grego", "græsk", "gresk", "görög", "řečtina", "gréčtina", "grščina",
           "grčki", "graikų", "grieķu", "kreeka", "kreikka", "greacă"),
    "et": ("estonian", "eesti", "estnisch", "estonien", "ests", "estonio", "estone", "estoński",
           "estniska", "estoniano", "estisk", "észt", "estonština", "estónčina", "estonščina",
           "estonski", "estų", "igauņu", "viro", "estoniană"),
    "lv": ("latvian", "latviešu", "lettisch", "letton", "lets", "letón", "lettone", "łotewski",
           "lettiska", "letão", "lettisk", "lett", "lotyština", "latvijščina", "latvijski",
           "latvių", "läti", "latvia", "λετονικά", "letonă"),
    "lt": ("lithuanian", "lietuvių", "litauisch", "lituanien", "litouws", "lituano", "litewski",
           "litauiska", "litauisk", "litván", "litevština", "litovčina", "litovščina",
           "litavski", "leišu", "leedu", "liettua", "λιθουανικά", "lituaniană"),
    "is": ("icelandic", "íslenska", "isländisch", "islandais", "ijslands", "islandés",
           "islandese", "islandzki", "isländska", "islandês", "islandsk", "izlandi",
           "islandština", "islandčina", "islandščina", "islandski", "islandų", "islandiešu",
           "islandi", "islanti", "ισλανδικά", "islandeză"),
    "ga": ("irish", "gaeilge", "irish gaelic", "irisch", "irlandais", "iers", "irlandés",
           "irlandese", "irlandzki", "iriska", "irlandês", "irsk"),
    "mt": ("maltese", "malti", "maltesisch", "maltais", "maltees", "maltés", "maltański"),
    "lb": ("luxembourgish", "lëtzebuergesch", "luxemburgisch", "luxembourgeois", "luxemburgs",
           "luksemburski"),
    "cy": ("welsh", "cymraeg", "walisisch", "gallois", "welsh (cymraeg)"),
    "ca": ("catalan", "català", "katalanisch", "catalán", "catalano", "kataloński"),
    "tr": ("turkish", "türkçe", "türkisch", "turc", "turks", "turco", "turecki", "turkiska"),
    "ru": ("russian", "русский", "russisch", "russe", "ruso", "russo", "rosyjski", "ryska"),
    "uk": ("ukrainian", "українська", "ukrainisch", "ukrainien", "oekraïens", "ucraniano",
           "ucraino", "ukraiński", "ukrainska"),
    "ar": ("arabic", "العربية", "arabisch", "arabe", "árabe", "arabo", "arabski", "arabiska"),
    "zh": ("chinese", "mandarin", "中文", "chinesisch", "chinois", "chinees", "chino", "cinese",
           "chiński", "kinesiska"),
}


def _plain(name: str) -> str:
    """For comparing names: lower case, accents removed ("Français" and "francais" are alike)."""
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip()


_CODE_OF = {_plain(name): code for code, names in LANGUAGE_ALIASES.items() for name in names}


def language_code(name: str | None) -> str | None:
    """The ISO code of a language named in any of the ways above, or None if unknown."""
    return _CODE_OF.get(_plain(name or ""))


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
