# Jobcu progress

Jobcu is built in phases (see section 16 of [HANDOVER.md](HANDOVER.md)). Each phase is finished,
tested and shown to the owner before the next one starts. Decisions are in
[DECISIONS.md](DECISIONS.md).

## Right now

*Last updated: 2026-09-17, night.*

**Where we are:** Phase 1 (usable first version), most of it built, plus a big coverage step:
Ireland now has sources, and companies' own career sites are read in every search. Everything is
committed and pushed, and GitHub's tests pass on macOS and Windows.

**Last finished (2026-09-17, night): many more job sources.**
- **JobsIreland.ie** (the Irish public employment service): Ireland's first source.
- **Company career sites** in six systems (Greenhouse, Lever, Ashby, Workable, Recruitee,
  Workday), read through the public job lists those systems publish, with a checked **employer
  directory of 240 companies** (`src/jobcu/data/employers.json`, refreshed with
  `tools/check_employers.py`): 115 hire in Ireland, 189 in the UK, 165 in Germany.
- **Arbeitnow** (free public API): many German and British jobs from career systems.
- `placenames.py` tells which country a free-text location is in ("Dublin, Ireland" vs
  "Dublin, CA"), and `sources/matching.py` matches titles and named places on Jobcu's side.
- **Adzuna and Reed keys are now optional** (README, guides and the setup checklist say so),
  because Jobcu finds jobs without any job-site key.
- Checked and **not** used: **EURES** (its terms allow automated extraction only for EURES partner
  organisations), **UK Find a Job** (blocks Jobcu), **SmartRecruiters** (robots.txt allows only
  LinkedIn). Details and every address in [SOURCES.md](SOURCES.md).

**Real tests (2026-09-17, night, the owner's own documents and keys, on a copy of his data
folder so his own results were untouched):**
- *Ireland, 72 hours*: 94 seconds, 0 matching hardware jobs. His search words are narrow
  ("Power Electronics Engineer", "Hardware Design Engineer", …) and Ireland has few such jobs.
- *Munich or within 50 km, 24 hours*: 145 seconds, 19 ads, 9 scored and shown (top: Franka
  Robotics 84, HENSOLDT 84). Career sites added nothing here: their job lists give a place as
  text, so **"within 50 km" can't be checked yet** and only jobs naming Munich itself are kept.
- Source test without AI (Germany + UK, 24 hours, broader words): 154 ads, of which career sites
  19 (Airbus, Octopus Energy, Ramp…) and Arbeitnow 18.

**Waiting on the owner (Utku):**
1. **A friend is testing Jobcu.** The owner invites him on GitHub himself. Collect the friend's
   feedback (installation, confusing steps, results) and fix what it shows.
2. **Run a real search himself** and give feedback: do the top results look right, is anything
   scored too high or too low, were titles "left out as clearly unrelated" (Search details)
   actually relevant?
3. Optional: a **generic cover letter**. The uploaded one is written for Tesla. The generic one
   should say he's open to any electronic hardware design field, with power electronics preferred
   and aerospace and defence also of interest.
4. **Decide about Jooble and Careerjet** (aggregators covering Ireland, the UK and Germany).
   Their free keys are meant for websites that show their jobs, and Jobcu has no website, so the
   owner should decide whether to sign up. Ask him before doing anything.

**Countries:** 30 European countries (see `countries.py` and DECISIONS.md). Search words use only
English plus the languages of the places searched.
**Coverage goal:** as many jobs as possible across **all 30** supported countries, from as
many platforms and routes as possible (not only APIs), without legal risk. **Ireland, UK and
Germany are worked on and tested first**; that's the order of work, not a limit.

**Next tasks for the assistant, in this order:**
1. **Places within a distance, for sources that give only a place name** (career sites,
   Arbeitnow). Today a job is kept only if its location text names the place, so "Munich or
   within 50 km" misses a career-site job in Garching. This needs coordinates for places and
   towns, which is Phase 2 work (HANDOVER §6 datasets) but costs coverage now.
2. **More employers in the directory**, especially Ireland, the UK and Germany, and more career
   systems: SAP SuccessFactors, Personio (its job pages need JavaScript), Softgarden, Teamtailor,
   JOIN, Oracle and iCIMS. `tools/check_employers.py` adds and checks candidates in one run;
   `find_workday.py` style discovery (a Workday site's robots.txt names its career sites) works
   well. Also consider reading employer career pages through `jobposting.py`.
3. **Optimise API use without losing quality** (DECISIONS.md, "Countries, reusing AI work,
   optimising requests"):
   - ~~**Profile reuse**~~ **done (2026-09-17)**: what the AI understood from the documents is
     kept in the data folder, keyed by the CV text, cover letter text, prompt, model and answer
     format, and reused while nothing changes. "What Jobcu understood" uses it too. Everything
     about the job search itself still runs fresh in every search.
   - **Remember job ad texts** by source and job ID for a few days, so the same ad isn't downloaded
     again.
   - **Provider-side prompt caching** where supported.
   - **Adaptive Adzuna budget** (`sources/adzuna.py`, `sources/budget.py`): replace the fixed 40
     requests per search with a share of what's left this month over the remaining days at about 3
     searches a day, never above what's left today (roughly 25–60 per search).
   - Workday costs about 3–5 requests per company per search (robots.txt, the filter list, then a
     page per country). Caching the country filter IDs in the directory would save one request per
     company, but risks missing jobs when an ID changes, so it wasn't done.
4. **Usage meter and limits in Settings** (HANDOVER §13): AI tokens for the last search and this
   month, estimated cost from an editable price table (no prices built in), optional monthly limit
   (already enforced in `ai/client.py`), scoring limit, source on/off switches
   (`settings.sources_disabled` exists, but there is no screen for it yet, and there are 11
   sources now), and Adzuna requests used today and this month.
5. **Score check / quality test set** (HANDOVER §13, "quick review"): about 40 real ads with
   Claude's pre-filled ratings (good / okay / poor, plus blockers); a review page in Jobcu where
   the owner corrects them (stored in the data folder, never in the repository). Then measure
   scores against ratings and check:
   - the quick relevance check
   - batch size 4 vs 1
   - summary vs full ad
   - reasoning effort
   - **how wide the search words should be** (the Ireland test found nothing with narrow titles)

   Tune the prompt and record the results.
6. Keep `docs/guides/` short and in step with the screens; fix what the tester's feedback shows.
7. Confirm Phase 1 "Done when" with the owner, then plan Phase 2 (design choices already in
   DECISIONS.md).

**Useful facts:** source behaviour and limits are in [SOURCES.md](SOURCES.md).
- **Owner's data folder:** `~/Library/Application Support/Jobcu`, with keys `adzuna_app_id`,
  `adzuna_app_key`, `ai_gemini` and `reed_api_key`. He uses Google Gemini, model
  `gemini-3.8-flash`, on the free allowance with no billing.
- **Real search timing now:** Munich 50 km, 24 hours ≈ 2.5 minutes (sources alone about 2
  minutes: Workday 331 requests, Greenhouse 49, Adzuna 28, Bundesagentur 36).
- **Checking the employer directory** takes about 10 minutes for 300 companies:
  `uv run python tools/check_employers.py candidates.json --write`.

---

| Phase | What it delivers | Status |
|---|---|---|
| 0. Foundations | Project set-up; Jobcu starts with a double-click | ✅ Done (2026-09-17) |
| 1. Usable first version | A real search with ranked, deduplicated results and reasons | 🔨 In progress |
| 2. Smart location filter | Understands sentences like "a city by the seaside" | Planned |
| 3. Maximum coverage | Many more job sources in every supported country | Planned |
| 4. Ready for friends | Complete guides, first-run setup, tested on real Mac and Windows computers | Planned |

---

## Phase 0: Foundations ✅

- [x] Plan and technology explained to the owner in plain language
- [x] Tools installed on the owner's Mac (uv, which also installs Python)
- [x] Private GitHub repository created
- [x] Owner's keys obtained (his own AI provider, Adzuna, Reed) and kept in his password manager,
      never in the project. Steps written up in [guides/getting-your-keys.md](guides/getting-your-keys.md)
- [x] Project skeleton, `.gitignore`, key storage, separate local data folder
- [x] `docs/DECISIONS.md`, plain-language README, `LICENSE` notice, `docs/HANDOVER.md`
- [x] Safety check that blocks keys and personal data (before each commit and on GitHub)
- [x] Automatic tests on macOS and Windows, including starting Jobcu with the real launchers
- [x] Instructions for friends and their AI coding assistants: [CONTRIBUTING.md](../CONTRIBUTING.md),
      [AGENTS.md](../AGENTS.md)
- [x] **Done when:** Jobcu starts on the owner's Mac with one double-click and shows an empty
      screen. Confirmed by the owner on 2026-09-17.
- Backups: the owner decided GitHub is enough (see DECISIONS.md)

## Phase 1: Usable first version 🔨

- [x] Universal AI provider layer: native Anthropic, Google Gemini and OpenAI, plus a generic
      OpenAI-compatible option; rate-limit handling; setup check (HANDOVER §13)
- [x] Settings screen: choose provider and model, enter keys (saved only on the computer),
      test the AI connection and the Adzuna and Reed keys
- [x] Owner entered his keys in Jobcu and all three tests pass (2026-09-17)
- [x] CV and cover letter upload (PDF, DOCX, TXT) and reading, with a "What Jobcu understood"
      preview of the profile (§3, §4)
- [x] First real test on the owner's own documents (2026-09-17): 8 seconds, about 5,500 tokens
- [x] Owner confirmed "What Jobcu understood" is right (2026-09-17). He is open to any field of
      electronic hardware design (power electronics preferred, aerospace and defence also of
      interest) and will put this in his generic cover letter
- [x] Search screen: location box, "Posted within", job types, "Don't include remote jobs",
      live progress, "What Jobcu understood" and "Search details" (§3)
- [x] Simple location input: explicit places and countries; other conditions shown as "not
      checked yet" until Phase 2 (§6)
- [x] Hidden multilingual search words: English plus the job-ad languages of the countries
      searched (§5). First real run: 73 search words in 4 languages, about 10 seconds
- [x] Time filter and job type filter applied to the jobs found (§7, §8)
- [x] Starter sources: Adzuna, Bundesagentur für Arbeit, Reed (§9)
- [x] More sources for Ireland, the UK and Germany (2026-09-17): JobsIreland.ie, Arbeitnow, and
      companies' own career sites in six systems with an employer directory of 240 companies.
      This brings §9.3 forward from Phase 3 (see DECISIONS.md)
- [x] Duplicate detection with main-link priority, "Also on" and "possible duplicate" (§10)
- [x] Rules filter and quick relevance check, with counts and left-out titles in Search details
- [ ] Quality test set of 30–50 real job ads judged by the owner, and a tuned scoring prompt (§13)
- [x] Scoring with 1–3 reasons per job (§11). First real search (Munich, 72 hours): 46 ads,
      41 different jobs, 22 scored, under 2 minutes
- [x] Results screen with Save / Applied / Not interested, "New" badge, Saved and Applied lists,
      "Show hidden", sorting, "Posting date unknown" section (§12)
- [x] Owner decided Jobcu may read Adzuna's job pages for full ads; now 18+ of 22 jobs are scored
      from full ads in a real search
- [x] Scoring limit that asks before scoring more (§13)
- [ ] Usage meter (per search and per month), monthly limits and price table in Settings (§13)
- [ ] **Done when:** the owner can run a real search on his Mac and get a ranked, deduplicated list
      with reasons.

## Phase 2: Smart location filter

- [ ] Location interpretation shown with the results, with an Edit option
- [ ] Reference datasets from HANDOVER §6 (places, boundaries, coastlines, UK sponsor register,
      German election results, country facts)
- [ ] **Done when:** all example sentences in HANDOVER §6 behave as described.

## Phase 3: Maximum coverage

- [ ] Source registry for every supported country (§9.0)
- [ ] All source types from §9.2–9.6: more career systems (SuccessFactors, Personio, Softgarden,
      Teamtailor, JOIN, Oracle, iCIMS) and a bigger employer directory. Six systems and a
      240-company directory already arrived in Phase 1 (2026-09-17), and the generic `JobPosting`
      reader exists since Phase 1 and reads Adzuna's job pages
- [ ] General live AI web search
- [ ] Per-source status, unique-job counts and on/off settings
- [ ] **Done when:** the coverage test shows no large avoidable gaps, and the remaining gaps are
      explained to the owner.

## Phase 4: Ready for friends

- [ ] Full manual test on a real Windows computer and a real Mac
- [ ] Complete everyday-user guides (§2.1), tested on clean computers
- [ ] First-run setup screen and polished double-click launchers
- [ ] Updating from GitHub while keeping the data folder
- [ ] Move the repository to a free GitHub organization and invite friends, choosing with the owner
      how friends can contribute (see DECISIONS.md)
