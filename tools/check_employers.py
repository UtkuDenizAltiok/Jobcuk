"""Checks and updates the employer directory (src/jobcu/data/employers.json).

For every employer it reads the company's job list once (one request for most career systems)
and records the supported countries it has jobs in, and whether it also hires elsewhere.
Employers without any job in the supported countries, or whose job list no longer exists, are
dropped and listed.

Usage:
    uv run python tools/check_employers.py                      check the directory as it is
    uv run python tools/check_employers.py new.json --write     add candidates and save

A candidates file has the same shape as the directory:
    {"employers": [{"name": "Acme", "system": "greenhouse", "board": "acme"}]}

Contacts only the career systems' public job lists, at Jobcu's polite pace. Run it now and then
(and before releases) so the directory stays current.
"""

import argparse
import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jobcu.keystore import KeyStore  # noqa: E402
from jobcu.placenames import OTHER  # noqa: E402
from jobcu.sources import career_sources  # noqa: E402
from jobcu.sources.base import SourceContext, SourceReport  # noqa: E402
from jobcu.sources.careers import DIRECTORY, Employer, EmployerNotFound  # noqa: E402
from jobcu.sources.http import PoliteClient  # noqa: E402

MAX_TOWNS = 40  # per country: enough to tell where a company hires without bloating the file

ABOUT = (
    "Employers in Jobcu's supported countries and the career system they use. General "
    "reference data from public career sites, never built from anyone's searches. Checked "
    "and updated with tools/check_employers.py; 'countries' are the supported countries the "
    "employer had jobs in when checked, 'elsewhere' means it also had jobs outside them."
)


def read_entries(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["employers"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("candidates", nargs="*", type=Path)
    parser.add_argument("--write", action="store_true", help="save the checked directory")
    args = parser.parse_args()

    entries: dict[tuple[str, str], dict] = {}
    existing = set()
    if DIRECTORY.exists():
        existing = {(e["system"], e["board"].strip().lower()) for e in read_entries(DIRECTORY)}
    for path in [DIRECTORY, *args.candidates]:
        if not path.exists():
            continue
        for entry in read_entries(path):
            key = (entry["system"], entry["board"].strip().lower())
            entries.setdefault(key, entry)

    sources = {source.system: source for source in career_sources()}
    unknown = sorted({system for system, _ in entries if system not in sources})
    if unknown:
        print(f"Unknown career systems: {', '.join(unknown)}")
        return 1

    http = PoliteClient()
    kept: list[dict] = []
    dropped: list[str] = []
    lock = threading.Lock()

    def check_system(system: str) -> None:
        source = sources[system]
        for key, entry in entries.items():
            if key[0] != system:
                continue
            employer = Employer(entry["name"], system, entry["board"], ())
            report = SourceReport(source.id, source.name)
            ctx = SourceContext(http, KeyStore(), report, lambda: False, lambda message: None)
            try:
                survey = source.survey(employer, ctx)
                counts: Counter = survey.counts
            except Exception as exc:  # noqa: BLE001 - a problem with one employer never stops the rest
                with lock:
                    if key in existing and not isinstance(exc, EmployerNotFound):
                        kept.append(entry)  # a passing network problem: keep what's known
                        print(f"{system:10} {entry['name']:35} kept unchecked ({exc})")
                    else:
                        dropped.append(f"{system:10} {entry['name']}: {exc or type(exc).__name__}")
                continue
            countries = sorted(code for code in counts if code not in (OTHER, "unknown"))
            line = (f"{system:10} {entry['name']:35} " +
                    " ".join(f"{code}:{counts[code]}" for code in countries) +
                    (f"  elsewhere:{counts[OTHER]}" if counts[OTHER] else ""))
            with lock:
                if countries:
                    kept.append({"name": entry["name"], "system": system,
                                 "board": entry["board"], "countries": countries,
                                 "elsewhere": bool(counts[OTHER]),
                                 "towns": {code: sorted(survey.towns.get(code, ()))[:MAX_TOWNS]
                                           for code in countries if survey.towns.get(code)}})
                    print(line, flush=True)
                else:
                    dropped.append(f"{system:10} {entry['name']}: no jobs in supported countries "
                                   f"({sum(counts.values())} elsewhere)")

    systems = sorted({system for system, _ in entries})
    with ThreadPoolExecutor(max_workers=len(systems) or 1) as pool:
        list(pool.map(check_system, systems))
    http.close()

    print(f"\nKept {len(kept)} employers, dropped {len(dropped)}:")
    for line in sorted(dropped):
        print(f"  {line}")
    if args.write:
        kept.sort(key=lambda e: (e["system"], e["name"].casefold()))
        data = {"about": ABOUT, "checked": datetime.now(UTC).date().isoformat(),
                "employers": kept}
        DIRECTORY.parent.mkdir(parents=True, exist_ok=True)
        DIRECTORY.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
        print(f"Saved {DIRECTORY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
