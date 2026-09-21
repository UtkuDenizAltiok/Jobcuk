# Jobcu progress

Jobcu is built in phases (see section 16 of [HANDOVER.md](HANDOVER.md)). Each phase is finished,
tested and shown to the owner before the next one starts. Decisions are in
[DECISIONS.md](DECISIONS.md).

## Right now

*Last updated: 2026-09-21 (late evening). Tree clean, all pushed, CI green, 362 tests pass.*

**Where we are:** Phase 1 is essentially complete. Phase 2 (the location box as a research task
for the AI) works, and **people can now correct it after a search** with the Edit button.
Coverage grows source by source: **16 sources** now (8 of them company career systems), with
Sweden and two more career systems added today and **357 employers** in the directory. Everything
is committed and pushed; GitHub's tests pass on macOS and Windows.

**Last finished (2026-09-21, late evening): travel limits to reference places**

The owner saw a job in Fürstenfeldbruck left out by *"at most 50 minutes to a city with at least
0.3% of the country's people"*: Jobcu had read it as "the job's own town has 0.3%". Now:
- **A limit to reference places is one condition** (`kind="near"` in `location.py`): minutes and
  a way of travelling (or km), measured to towns of a size, named towns or kinds of places the AI
  looks up. The AI reads each person's wording; nothing is built in. Checked live with the
  owner's Gemini: it read the owner's sentence exactly so (50 min, transit, 0.3%).
- **`travel.py` measures it:** job position from the job site's coordinates, else the town centre;
  straight-line bounds settle clear cases; Google Maps (Routes API, weekday 8:00) for the 3
  nearest reference places, only for jobs that passed the quick check; jobs within 10 minutes
  of the limit measured again from the company's address (Places); without a key, AI estimates,
  labelled. Monthly limits below Google's free allowance (Settings → Travel times, with a test
  button). Minutes are kept per job, so Edit applies a new limit instantly.
- Live test (Munich or within 40 km, 72 h, no Maps key): Weßling and Gilching kept at an
  estimated 40–45 minutes to Munich, Neuching left out at 65; tightening to 30 minutes in Edit
  moved them out with no new requests.
- Also fixed: an import loop from the SuccessFactors module (a new test loads every key module in
  a fresh Python).

**Earlier on 2026-09-21**

- **"Edit" next to "Understood as"** (HANDOVER §6, point 2). A window lists each condition about
  places: switch it off, correct its list of towns or its town size, reword it (Jobcu checks it
  again with the AI), ask for a new check, or add a condition. The changes are applied to the jobs
  the search already found, without searching again: only jobs that come back in are quick-checked
  and scored, and every earlier answer is reused. The latest search's jobs are kept for this
  (`pool.py`, table `search_pool`; the next search replaces them). Search and correction share one
  final step (`search._decide`). Checked live on a copy of the owner's data: Munich + "at least
  1 million people", then switched off and replaced by "at least 20,000 people".
- **Bug found in that live test and fixed:** Adzuna writes "Unterhaching, München (Kreis)"; the
  town finder took the district for the city of Munich, so suburbs passed a big-city condition.
  Districts and counties ("(Kreis)", "Co. Cork", "County …") now count only when no town is named.
- **Arbetsförmedlingen (Sweden)** is a source: its open JobSearch API (CC0, no key). Jobcu reads
  every ad in the time window and matches on its own side, because the API's word search misses
  Swedish compound words. 24 hours ≈ 16 requests, 10 s. Details in SOURCES.md.
- **Teamtailor** (seventh career system): every Teamtailor career site's RSS feed (full ads, exact
  times, places). **SuccessFactors** (eighth): the sitemap each site publishes for search engines;
  a job's own page is opened only when its title matches the search words (date, place and full
  ad are on the page). Only sites whose pages carry that data are in the directory (SAP,
  Schaeffler, ZF, KUKA, Festo, Endress+Hauser); Danfoss, SICK, Vitesco, Wacker need JavaScript and
  MTU's pages redirect: left out, see SOURCES.md. Career systems now get the search words as a
  hint, and share one robots.txt check (`CareerSystemSource.allowed`).
- **Employer directory: 357 companies** (was 326; IE 149, UK 259, DE 232), re-checked today.
  Found via web searches and by probing `jobs.{company}.com`. `tools/check_employers.py
  candidates.json --only-new --write` checks only new candidates (seconds instead of 15 minutes).
- **Terms of the job boards on hold** (IrishJobs.ie, Jobs.ie, Totaljobs, StepStone.de, all Stepstone
  Group) are read and recorded in SOURCES.md: none clearly allows automated reading, StepStone.de
  names scraping. They stay on hold.
- README no longer says the smart checks are still to come; the first-search guide explains Edit.

**Earlier (2026-09-17):** 11 sources (JobsIreland.ie, jobs.ac.uk, EURAXESS, Arbeitnow, six
company career systems with a 326-company employer directory, Adzuna, Reed, Bundesagentur), the
location conditions researched live or computed from the shipped town list (GeoNames), the Score
check screen and `tools/score_check.py`, the usage meter with limits and source switches, profile
reuse, ad texts reused for three days, Adzuna's allowance shared across the month, prompt caching,
`tools/coverage_test.py`. Real tests then: Germany with the far-right and 0.3% conditions (4 min,
251 jobs, 139 left out by the conditions, 56 shown); Munich 24 h; Ireland 72 h.

**Waiting on the owner (Utku):**
1. **A friend is testing Jobcu.** Collect his feedback (installation, confusing steps, results).
2. **Run a real search yourself** and say whether the top results look right. The **Score check**
   screen (top menu) collects a few jobs from each search: answer good / okay / poor. His data
   folder shows no search since 2026-09-17, so nothing is rated yet.
3. Optional: a **generic cover letter** (the uploaded one is written for Tesla).
4. **A coverage list, to measure what Jobcu misses:** 15–25 jobs you'd want Jobcu to find (from
   LinkedIn, StepStone, Indeed, anywhere), one per line: `Company | Job title | Place | link`. Then
   `uv run python tools/coverage_test.py that-file.txt` says how many Jobcu found and why not.
5. **Google Maps key, now built in and waiting for your key:** real public-transport times for
   conditions like yours. It needs a Google Cloud account with billing (a card), but stays in the
   free allowance; the steps are in `docs/guides/getting-your-keys.md`, and the assistant will
   walk you through them one at a time.
6. **The job boards on hold** (IrishJobs.ie, Jobs.ie, Totaljobs, StepStone.de): their terms are
   now summarised in SOURCES.md. Options: keep them on hold (today's rule), or write to the
   Stepstone Group asking permission for personal, device-local use. Best decided with the
   coverage list's numbers.
7. **One question:** may facts that barely change (a town's population, the last election's
   results) be remembered with their source and date for a while, or should every search look them
   up again? Everything about the *jobs* stays fresh either way.
8. **Jooble and Careerjet** need free keys meant for websites showing their jobs, and Jobcu has no
   website. **France Travail, Norway's NAV and Belgium's VDAB** need a free registration or key.
   Your call whether to sign up for any of them.

**Countries:** 30 European countries (see `countries.py`). Search words use English plus the
languages of the places searched.
**Coverage goal:** as many jobs as possible across all 30, through every legally safe route.
Ireland, the UK and Germany are worked on and tested first.

**Next tasks for the assistant, in this order:**
1. **Use the score-check loop once the owner has answered a few jobs** (`tools/score_check.py`:
   compare, or `--rescore --batch 1 --effort medium --summary` to tune; HANDOVER §13).
2. **More coverage, IE/UK/DE first:** more employers in the directory (especially Teamtailor
   companies in Ireland and the UK, and SuccessFactors sites of German engineering firms; MTU Aero
   Engines' job pages redirect and are worth a closer look), more career systems (Personio,
   Softgarden, BambooHR, Comeet, Oracle), and national public employment services with open data
   and no key (candidates: Czechia's MPSV open data, Poland's CBOP, Finland, Estonia, Slovenia,
   Luxembourg). Check terms and robots.txt first and record each in SOURCES.md. Possible saving:
   SuccessFactors pages opened for address-list sites aren't remembered between searches yet
   (only feed sites' dates are); remembering title, place and date for three days would cut
   repeat requests.
3. **More of Phase 2:** walk the owner through the Google Maps key when he's ready (one step
   at a time, `docs/guides/getting-your-keys.md`), then run a real search with it and compare
   Google's times with the AI's estimates. Remember researched facts and travel times between
   searches if he allows it (question 7). Possible next kind of reference place: kinds of places
   near the job itself (a train station, Turkish supermarkets) through Places nearby search.
4. Keep `docs/guides/` in step with the screens; fix what the tester's feedback shows.
5. Confirm Phase 1 "Done when" with the owner, then agree what Phase 2 must still deliver.

**Useful facts:** source behaviour and limits are in [SOURCES.md](SOURCES.md).
- **Owner's data folder:** `~/Library/Application Support/Jobcu`, keys `adzuna_app_id`,
  `adzuna_app_key`, `ai_gemini`, `reed_api_key`. Google Gemini, model `gemini-3.8-flash`, free
  allowance, no billing. **Web search works on that free allowance** (checked live).
- **Timing now:** a German 24-hour search takes about 4 minutes (sources about 2, of which Workday
  is the slowest at ~400 requests when no place is named).
- **Never run searches against his real data folder:** copy it to a scratch folder first
  (`cp -R "$HOME/Library/Application Support/Jobcu" /tmp/…`) and point `JOBCU_DATA_DIR` at the copy.
- **Checking the employer directory** takes about 15 minutes for 350 companies:
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
- [x] Usage meter (per search and per month), monthly limits, price table and job source
      switches in Settings (§13)
- [ ] **Done when:** the owner can run a real search on his Mac and get a ranked, deduplicated list
      with reasons.

## Phase 2: Smart location filter

The location box is a research task for the AI, not a filter (DECISIONS.md, 2026-09-17 night).

- [x] The AI splits the location text into conditions and picks a way to check each one
      (2026-09-17)
- [x] **Live web search** for conditions that need facts (elections, shops, students, anything
      else), with the sources kept and shown (2026-09-17)
- [x] **Real travel times** (Google Maps, weekday working hours, within the free allowance),
      one request per place and not per job (built 2026-09-21; waiting for the owner's key, AI
      estimates until then)
- [x] Location interpretation shown with the results, with an Edit option, sources and clearly
      marked estimates (Edit: 2026-09-21)
- [ ] Reference data from HANDOVER §6 as *rulers* only: the town list already ships (coordinates,
      population, local names); boundaries, coastlines, the UK sponsor register and election
      results as needed
- [ ] **Done when:** the example sentences in HANDOVER §6, in README.md and the owner's own
      examples behave as described, each with its working shown.

## Phase 3: Maximum coverage

- [ ] Source registry for every supported country (§9.0)
- [ ] All source types from §9.2–9.6: more career systems (SuccessFactors, Personio, Softgarden,
      Teamtailor, JOIN, Oracle, iCIMS) and a bigger employer directory. Six systems and a
      240-company directory already arrived in Phase 1 (2026-09-17), and the generic `JobPosting`
      reader exists since Phase 1 and reads Adzuna's job pages
- [ ] General live AI web search
- [x] Per-source status, unique-job counts and on/off settings (Phase 1, 2026-09-17)
- [ ] **Done when:** the coverage test shows no large avoidable gaps, and the remaining gaps are
      explained to the owner.

## Phase 4: Ready for friends

- [ ] Full manual test on a real Windows computer and a real Mac
- [ ] Complete everyday-user guides (§2.1), tested on clean computers
- [ ] First-run setup screen and polished double-click launchers
- [ ] Updating from GitHub while keeping the data folder
- [ ] Move the repository to a free GitHub organization and invite friends, choosing with the owner
      how friends can contribute (see DECISIONS.md)
