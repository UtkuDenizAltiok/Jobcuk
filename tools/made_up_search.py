"""Runs one complete Jobcu search for a made-up person, to measure what a change does.

The default person is a graduate engineer in electronics and power electronics hardware, the
kind of work tested first and most (DECISIONS.md, "The owner's priorities"); the CV and cover
letter are made up here, never anyone's real documents. The search runs inside Jobcu itself
(every source, the person's AI provider from the settings), and the tool prints what each
source found and the best cards.

    JOBCU_DATA_DIR=/some/empty/folder uv run python tools/made_up_search.py
    ... --where "Munich or within 40 km, or Dublin" --hours 72

It needs a data folder of its own: it saves the made-up documents there, so it refuses a folder
that holds anyone's real documents. Choose the AI provider, model and key for that folder in
Jobcu's settings first (or save them with a short script). Costs a real search's AI tokens.
"""

import argparse
import io
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jobcu import documents, paths  # noqa: E402
from jobcu.settings import load_settings  # noqa: E402

MARKER = "made-up-person.txt"

CV = """Curriculum Vitae
Graduate electrical engineer specialising in power electronics hardware.
Education: MSc Electrical Engineering (power electronics), 2026; BSc Electrical Engineering, 2024.
Master's thesis: design and test of a 3 kW bidirectional DC/DC converter with GaN transistors.
Experience: 2024-2026 working student, hardware development at an industrial drives company:
schematics and PCB layout (Altium Designer), LTspice simulation, gate-driver boards, lab
measurements with oscilloscopes and power analysers. 2023 internship: EMC pre-compliance tests.
Skills: power electronics, DC/DC and inverter topologies, analogue circuit design, PCB design,
magnetics basics, MATLAB/Simulink, Python for lab automation.
Languages: English (C1), German (B1), Italian (native)."""

LETTER = """Dear hiring team, I am looking for my first full-time role in hardware or power
electronics development, ideally designing converters or inverters for industrial, automotive
or energy products. I can work in English and am improving my German."""


def prepare_folder() -> None:
    folder = paths.data_dir()
    marker = folder / MARKER
    has_documents = any(documents.get_info(kind) for kind in ("cv", "cover_letter"))
    if has_documents and not marker.exists():
        sys.exit(f"{folder} holds someone's documents. Use an empty data folder for this tool.")
    marker.write_text("This data folder belongs to tools/made_up_search.py.\n", encoding="utf-8")
    import docx

    document = docx.Document()
    for line in CV.splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    documents.save_upload("cv", "cv.docx", buffer.getvalue())
    documents.save_upload("cover_letter", "letter.txt", LETTER.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--where", default="Munich or within 40 km, or Dublin")
    parser.add_argument("--hours", type=int, choices=[6, 24, 72, 168], default=24)
    parser.add_argument("--show", type=int, default=15, help="how many cards to print")
    args = parser.parse_args()
    if not load_settings().ai.provider:
        print("Choose an AI provider for this data folder first (Jobcu's Settings).")
        return 1
    prepare_folder()

    from fastapi.testclient import TestClient

    from jobcu.app import create_app

    client = TestClient(create_app(), base_url="http://127.0.0.1")
    headers = {"X-Jobcu": "1"}
    form = {"location_text": args.where, "about_you": "", "posted_within_hours": args.hours,
            "job_types": ["full_time_permanent", "fixed_term"], "exclude_remote": False}
    response = client.post("/api/search", json=form, headers=headers)
    if response.status_code != 200:
        print("The search didn't start:", response.text)
        return 1
    started, shown = time.time(), ""
    while True:
        run = client.get("/api/search/current").json()["search"]
        line = " · ".join(f"{s['label']}: {s['status']}" for s in run["steps"]
                          if s["status"] == "running")
        if line and line != shown:
            print(f"{time.time() - started:5.0f} s  {line}")
            shown = line
        if run.get("question"):
            print("Question:", run["question"].get("text", run["question"]), "→ yes")
            client.post(f"/api/search/{run['id']}/answer", json={"yes": True}, headers=headers)
        if run["status"] not in ("running", "waiting"):
            break
        time.sleep(3)
    print(f"\nSearch {run['status']} in {time.time() - started:.0f} s. {run.get('error') or ''}")
    for note in run.get("notes") or []:
        print("Note:", note)
    jobs = (run.get("result") or {}).get("jobs") or {}
    print("\nSources (jobs found / only here / requests):")
    for source in jobs.get("sources") or []:
        if source["status"] != "skipped":
            print(f"  {source['name']:45} {source['jobs_found']:4} {source.get('unique', 0):4} "
                  f"{source['requests']:5}  {source['status']} {source.get('message') or ''}")
    cards = jobs.get("cards") or []
    print(f"\n{len(cards)} jobs shown. The best:")
    for card in cards[: args.show]:
        limits = "; ".join(limit["why"] for limit in card.get("limits") or [])
        print(f"  {card.get('score') or '–':>3}  {card['title'][:60]} | {card.get('company')} | "
              f"{card.get('location')} | {card['main_link']['source']}"
              f"{' | summary only' if card.get('summary_only') else ''}"
              f"{' | ' + limits if limits else ''}")
    return 0 if run["status"] == "finished" else 1


if __name__ == "__main__":
    sys.exit(main())
