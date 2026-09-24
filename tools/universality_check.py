"""Checks that Jobcu works for people outside engineering (AGENTS.md: "Jobcu is universal").

Five made-up people from other fields and countries go through what the person's AI does in a
search: reading the CV into a profile, writing the hidden search words, the quick check that
leaves out clearly unrelated jobs, and scoring. Everything is made up in this file: no real CV,
no real job ad. The search words are also compared with ESCO, the EU's open list of occupations
and their names in every EU language, to see which common job titles the words would miss.

    uv run python tools/universality_check.py                     every person, once
    uv run python tools/universality_check.py --person nurse      one person
    uv run python tools/universality_check.py --runs 2 --out report.json

It uses the AI provider and model saved in Jobcu's settings (JOBCU_DATA_DIR chooses the data
folder) and costs tokens: about 5 requests per person and run. ESCO needs no key.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jobcu.ai.client import AIClient  # noqa: E402
from jobcu.ai.usage import UsageLog  # noqa: E402
from jobcu.dedupe import group_duplicates  # noqa: E402
from jobcu.keystore import KeyStore  # noqa: E402
from jobcu.keywords import generate_search_words  # noqa: E402
from jobcu.location import LocationPlan  # noqa: E402
from jobcu.profile import read_profile  # noqa: E402
from jobcu.relevance import quick_pass  # noqa: E402
from jobcu.scoring import score_groups  # noqa: E402
from jobcu.settings import load_settings  # noqa: E402
from jobcu.sources.base import FoundJob  # noqa: E402
from jobcu.sources.matching import term_matches  # noqa: E402

ESCO = "https://ec.europa.eu/esco/api"


@dataclass
class Ad:
    title: str
    company: str
    place: str
    country: str
    text: str
    expect: str  # "high", "middle" or "low": what a careful reader would score


@dataclass
class Person:
    key: str
    cv: str
    languages: list[str]  # the search-word languages a search there would use
    esco_query: tuple[str, str]  # an occupation name and its language, to find it in ESCO
    ads: list[Ad]
    related_titles: list[str] = field(default_factory=list)  # quick check must keep these


PEOPLE = [
    Person(
        key="teacher",
        cv="""Curriculum vitae
Leerkracht lager onderwijs met 6 jaar ervaring in het basisonderwijs in Gent.
Ervaring: 2020-heden: klasleerkracht 3de en 4de leerjaar, Basisschool De Linde (Gent).
2019-2020: interimaris lager onderwijs, verschillende scholen in Oost-Vlaanderen.
Opleiding: Bachelor in het onderwijs: lager onderwijs, Arteveldehogeschool Gent (2019).
Talen: Nederlands (moedertaal), Frans (goed, B2), Engels (goed, B2).
Sterktes: differentiatie, zorgbeleid, leesbevordering, STEM-projecten in de klas.
Ik zoek een vaste betrekking als leerkracht in het lager onderwijs, voltijds of 4/5.""",
        languages=["en", "nl"],
        esco_query=("leerkracht lager onderwijs", "nl"),
        related_titles=["Leerkracht lager onderwijs", "Zorgcoördinator basisschool"],
        ads=[
            Ad("Leerkracht 4de leerjaar (24/24)", "Vrije Basisschool Voorbeeld", "Gent", "BE",
               "Wij zoeken een enthousiaste leerkracht lager onderwijs voor het 4de leerjaar. "
               "Diploma bachelor lager onderwijs vereist. Vaste betrekking, voltijds.", "high"),
            Ad("Leraar Frans secundair onderwijs", "Atheneum Voorbeeld", "Gent", "BE",
               "Voor de tweede graad zoeken we een leraar Frans. Specifieke lerarenopleiding "
               "secundair onderwijs Frans vereist. Tijdelijke vervanging tot juni.", "middle"),
            Ad("Magazijnmedewerker", "Voorbeeld Logistics", "Gent", "BE",
               "Je laadt en lost vrachtwagens, heftruckattest is een plus. Ploegensysteem.",
               "low"),
        ],
    ),
    Person(
        key="nurse",
        cv="""CURRICULUM VITAE
Registered General Nurse (NMBI registered), 4 years in adult intensive care.
Experience: 2022-present: Staff Nurse, Intensive Care Unit, a university hospital in Cork
(ventilated patients, CRRT, sepsis management). 2021-2022: Staff Nurse, surgical ward.
Education: BSc (Hons) General Nursing, University College Cork (2021). ACLS, ILS.
Languages: English (native), Irish (B1).
Looking for a permanent full-time post in critical care in Cork or nearby.""",
        languages=["en"],
        esco_query=("nurse responsible for general care", "en"),
        related_titles=["Staff Nurse - Intensive Care Unit", "Clinical Nurse Manager 2 ICU"],
        ads=[
            Ad("Staff Nurse - Intensive Care Unit", "Example University Hospital", "Cork", "IE",
               "Permanent full-time Staff Nurse post in our 20-bed ICU. Candidates must be "
               "registered with NMBI. Experience in critical care is an advantage.", "high"),
            Ad("Clinical Nurse Specialist - Diabetes", "Example Hospital Group", "Cork", "IE",
               "Specialist post in diabetes care in outpatient clinics. Requires 5 years' "
               "post-registration experience and a postgraduate qualification in diabetes.",
               "middle"),
            Ad("Software Engineer (Python)", "Example Tech Ltd", "Cork", "IE",
               "Build backend services in Python and Go. Degree in computer science.", "low"),
        ],
    ),
    Person(
        key="chef",
        cv="""Lebenslauf
Koch EFZ mit 7 Jahren Erfahrung in der gehobenen Gastronomie.
2021-heute: Sous-Chef, Hotelrestaurant am See, Luzern (Brigade von 9, Einkauf, Menüplanung).
2018-2021: Chef de Partie Saucier, Restaurant in Zürich.
2015-2018: Lehre als Koch EFZ, Bern.
Sprachen: Deutsch (Muttersprache), Englisch (B1), Italienisch (A2).
Ich suche eine Stelle als Sous-Chef oder Küchenchef in Zürich, 100 %.""",
        languages=["en", "de"],
        esco_query=("sous chef", "en"),
        related_titles=["Sous-Chef (m/w/d) 100%", "Chef de Partie Garde-Manger"],
        ads=[
            Ad("Sous-Chef (m/w/d) 100%", "Beispiel Hotel AG", "Zürich", "CH",
               "Für unser Restaurant mit 80 Plätzen suchen wir einen Sous-Chef. Abgeschlossene "
               "Kochlehre EFZ und Führungserfahrung. Deutsch fliessend.", "high"),
            Ad("Leiter Gemeinschaftsgastronomie", "Beispiel Spital", "Winterthur", "CH",
               "Sie leiten die Personalküche eines Spitals mit 600 Mahlzeiten täglich, "
               "Budgetverantwortung, Weiterbildung zum Gastronomieleiter erwünscht.", "middle"),
            Ad("Buchhalter/in 80-100%", "Beispiel Treuhand GmbH", "Zürich", "CH",
               "Führen der Debitoren- und Kreditorenbuchhaltung, Fachausweis Finanz- und "
               "Rechnungswesen.", "low"),
        ],
    ),
    Person(
        key="lawyer",
        cv="""Lebenslauf
Volljurist (Zweites Staatsexamen 2022, Bayern), Rechtsanwalt seit 2022.
2022-heute: Rechtsanwalt im Arbeitsrecht, mittelständische Kanzlei in München
(Kündigungsschutz, Betriebsverfassungsrecht, Vertragsgestaltung).
Studium der Rechtswissenschaften, LMU München; Erstes Staatsexamen 2019.
Sprachen: Deutsch (Muttersprache), Englisch (verhandlungssicher).
Ich suche eine Stelle als Rechtsanwalt oder Syndikusrechtsanwalt im Arbeitsrecht in München.""",
        languages=["en", "de"],
        esco_query=("Rechtsanwalt", "de"),
        related_titles=["Rechtsanwalt (m/w/d) Arbeitsrecht", "Syndikusrechtsanwalt Arbeitsrecht"],
        ads=[
            Ad("Rechtsanwalt (m/w/d) Arbeitsrecht", "Beispiel Rechtsanwälte PartG", "München",
               "DE", "Wir suchen Rechtsanwälte mit zwei Prädikatsexamina und erster Erfahrung im "
               "Arbeitsrecht. Sehr gute Englischkenntnisse.", "high"),
            Ad("Syndikusrechtsanwalt Gesellschaftsrecht", "Beispiel AG", "München", "DE",
               "Rechtsabteilung eines Konzerns: M&A, Gesellschaftsrecht, Compliance. "
               "Mindestens 5 Jahre Berufserfahrung.", "middle"),
            Ad("Pflegefachkraft (m/w/d)", "Beispiel Klinikum", "München", "DE",
               "Examinierte Pflegefachkraft für die Innere Medizin, Schichtdienst.", "low"),
        ],
    ),
    Person(
        key="driver",
        cv="""Życiorys
Kierowca zawodowy, prawo jazdy kat. C+E, kwalifikacja wstępna, karta kierowcy, ADR.
2014-obecnie: kierowca w transporcie międzynarodowym (Niemcy, Holandia, Francja), chłodnie
i plandeki, 12 lat bez wypadku.
2012-2014: kierowca kat. C w dystrybucji krajowej, Poznań.
Języki: polski (ojczysty), niemiecki (A2).
Szukam pracy jako kierowca C+E w Poznaniu lub okolicy, najlepiej w transporcie krajowym.""",
        languages=["en", "pl"],
        esco_query=("kierowca samochodu ciężarowego", "pl"),
        related_titles=["Kierowca C+E transport krajowy", "Kierowca kat. C dystrybucja"],
        ads=[
            Ad("Kierowca C+E - transport krajowy", "Przykład Trans Sp. z o.o.", "Poznań", "PL",
               "Zatrudnimy kierowcę kat. C+E z kwalifikacją i kartą kierowcy. Umowa o pracę, "
               "powroty codziennie.", "high"),
            Ad("Dyspozytor transportu", "Przykład Logistyka", "Poznań", "PL",
               "Planowanie tras, kontakt z kierowcami, znajomość języka niemieckiego na "
               "poziomie komunikatywnym.", "middle"),
            Ad("Księgowa / Księgowy", "Przykład Biuro Rachunkowe", "Poznań", "PL",
               "Prowadzenie ksiąg rachunkowych, znajomość przepisów podatkowych.", "low"),
        ],
    ),
]

# Titles from many kinds of work, for the quick check: every person's own titles must be kept,
# and most of the rest left out.
MIXED_TITLES = [
    ("Leerkracht lager onderwijs", "Basisschool Voorbeeld"),
    ("Zorgcoördinator basisschool", "Basisschool Voorbeeld"),
    ("Staff Nurse - Intensive Care Unit", "Example Hospital"),
    ("Clinical Nurse Manager 2 ICU", "Example Hospital"),
    ("Sous-Chef (m/w/d) 100%", "Beispiel Hotel AG"),
    ("Chef de Partie Garde-Manger", "Beispiel Restaurant"),
    ("Rechtsanwalt (m/w/d) Arbeitsrecht", "Beispiel Kanzlei"),
    ("Syndikusrechtsanwalt Arbeitsrecht", "Beispiel AG"),
    ("Kierowca C+E transport krajowy", "Przykład Trans"),
    ("Kierowca kat. C dystrybucja", "Przykład Trans"),
    ("Hardware Design Engineer", "Example Devices"),
    ("Buchhalter/in 80-100%", "Beispiel Treuhand"),
    ("Warehouse Operative", "Example Logistics"),
    ("Sales Representative", "Example Retail"),
    ("Software Developer (Java)", "Example Tech"),
]


def as_group(title: str, company: str, place: str, country: str, text: str):
    job = FoundJob(source="made_up", source_job_id=title, url="https://example.invalid/job",
                   title=title, company=company, location_text=place, country=country,
                   description=text, description_is_complete=True)
    return group_duplicates([job], {"made_up": "job_board"})[0]


def esco_titles(query: str, language: str, languages: list[str]) -> dict[str, list[str]]:
    """The occupation's names in ESCO: its preferred and alternative labels per language."""
    with httpx.Client(timeout=30, headers={"User-Agent": "Jobcu (universality check)"}) as http:
        found = http.get(f"{ESCO}/search", params={
            "text": query, "type": "occupation", "language": language, "limit": 1,
        }).json()["_embedded"]["results"]
        if not found:
            return {}
        uri = found[0]["uri"]
        titles = {}
        for code in languages:
            data = http.get(f"{ESCO}/resource/occupation",
                            params={"uri": uri, "language": code}).json()
            names = [data.get("preferredLabel", {}).get(code, "")]
            names += data.get("alternativeLabel", {}).get(code, [])
            titles[code] = sorted({name for name in names if name})
        return titles


def check_person(client: AIClient, person: Person, plan: LocationPlan, esco: bool) -> dict:
    profile = read_profile(client, person.cv, "")
    words = generate_search_words(client, profile, person.languages)
    titles = [w for w in words if w.kind == "job_title"]
    report = {
        "person": person.key,
        "profile": {"field": profile.field, "role": profile.current_or_last_role,
                    "target_roles": profile.target_roles, "areas": profile.technical_areas,
                    "seniority": profile.seniority,
                    "languages": [f"{s.language} {s.cefr}" for s in profile.languages]},
        "search_words": {code: [w.text for w in words if w.language == code]
                         for code in person.languages},
    }
    if esco:
        names = esco_titles(*person.esco_query, person.languages)
        missed = {code: [name for name in found if not any(
            term_matches(w.text, name) for w in titles if w.language == code)]
            for code, found in names.items()}
        report["esco"] = {code: {"names": len(found), "missed": missed[code]}
                          for code, found in names.items()}
    groups = [as_group(title, company, "", "", "") for title, company in MIXED_TITLES]
    quick = quick_pass(client, profile, groups, list(range(len(groups))))
    left_out = [groups[i].main.title for i in quick.unrelated]
    report["quick_check"] = {
        "left_out": left_out,
        "wrongly_left_out": [t for t in person.related_titles if t in left_out],
    }
    ads = [as_group(a.title, a.company, a.place, a.country, a.text) for a in person.ads]
    scored = score_groups(client, profile, plan, ads, list(range(len(ads))))
    report["scores"] = [
        {"title": ad.title, "expect": ad.expect, "score": scored[i]["score"],
         "reasons": scored[i]["reasons"], "limits": scored[i].get("limits", [])}
        for i, ad in enumerate(person.ads) if i in scored
    ]
    return report


def show(report: dict) -> None:
    print(f"\n=== {report['person']}: {report['profile']['role'] or report['profile']['field']}")
    print(f"  target roles: {', '.join(report['profile']['target_roles'])}")
    for code, found in report["search_words"].items():
        print(f"  words ({code}): {', '.join(found)}")
    for code, esco in report.get("esco", {}).items():
        print(f"  ESCO ({code}): {esco['names'] - len(esco['missed'])} of {esco['names']} names "
              f"found; missed: {', '.join(esco['missed'][:12]) or 'none'}")
    quick = report["quick_check"]
    print(f"  quick check left out: {', '.join(quick['left_out']) or 'nothing'}")
    if quick["wrongly_left_out"]:
        print(f"  !! wrongly left out: {', '.join(quick['wrongly_left_out'])}")
    for score in report["scores"]:
        print(f"  {score['score']:3d} (expect {score['expect']}): {score['title']} - "
              f"{'; '.join(score['reasons'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--person", choices=[p.key for p in PEOPLE])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--no-esco", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    settings = load_settings()
    if not settings.ai.provider:
        print("Choose an AI provider in Jobcu's Settings first.")
        return 1
    client = AIClient(settings, KeyStore(), usage_log=UsageLog(), notify=print)
    plan = LocationPlan(text="", understood_as="Anywhere.", countries=[], places=[],
                        not_checked_yet=[], outside_supported_area=[], broad=True)
    reports = []
    for person in PEOPLE:
        if args.person and person.key != args.person:
            continue
        for run in range(args.runs):
            report = check_person(client, person, plan, esco=not args.no_esco and run == 0)
            report["run"] = run + 1
            show(report)
            reports.append(report)
    if args.out:
        args.out.write_text(json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
