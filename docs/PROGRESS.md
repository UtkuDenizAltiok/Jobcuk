# Jobcu progress

Jobcu is built in phases (see section 16 of [HANDOVER.md](HANDOVER.md)). Each phase is finished,
tested and shown to the owner before the next one starts. Decisions are in
[DECISIONS.md](DECISIONS.md).

## Right now

*Last updated: 2026-09-17, late night.*

**Where we are:** Phase 1 is essentially complete, and the two things the owner cares most about
moved a long way: **coverage** (Ireland now has sources, company career sites and several new job
sites are read in every search) and **the location box as a research task for the AI** (the first
version of Phase 2 works). Everything is committed and pushed; GitHub's tests pass on macOS and
Windows.

**Last finished (2026-09-17, night and late night)**

*More sources (11 now, from 3):*
- **JobsIreland.ie** (Irish public employment service), **jobs.ac.uk** (UK and Irish universities
  and research institutes), **EURAXESS** (research jobs all over Europe), **Arbeitnow** (free
  public API, many German and British jobs from career systems).
- **Company career sites** in six systems (Greenhouse, Lever, Ashby, Workable, Recruitee,
  Workday), with a checked **employer directory of 326 companies**
  (`src/jobcu/data/employers.json`, refreshed with `tools/check_employers.py`): 135 hire in
  Ireland, 245 in the UK, 216 in Germany, and every supported country has at least two. The
  directory also records **which towns** each company hires in, so a search for one city can skip
  companies that only hire far away.
- Checked and **not** used, with reasons in [SOURCES.md](SOURCES.md): EURES (its terms allow
  automated extraction only for EURES partners), UK Find a Job, UK Civil Service Jobs and
  publicjobs.ie (all answer with bot checks), SmartRecruiters (robots.txt allows only LinkedIn),
  Personio (its pages need JavaScript; many of its jobs arrive through Arbeitnow anyway).
- **Adzuna and Reed keys are now optional:** Jobcu finds jobs without any job-site key.

*The location box (Phase 2, first version):*
- The AI splits what someone writes into conditions and checks each one: **town-size conditions
  are computed** from the figures Jobcu ships (town populations, and people per country), and
  **anything else about a place is looked up live on the web** through the person's own AI
  provider, which returns the towns that fit or the towns to avoid **with its sources**.
- Conditions it can't confirm, and conditions about the job itself, are shown as "not checked" and
  never filter anything. Every job card says what each condition found, and jobs whose place can't
  be recognised are kept, not dropped.
- Jobcu also ships a town list (GeoNames, 63,220 towns with local names, coordinates and
  population) **as a ruler only**: it answers "where is this place and how big is it" once the AI
  has decided what to measure.

*Other work:* the **Score check** screen (every search keeps a few of its ads and left-out titles
for the owner to rate), a **usage meter with limits, a price table and on/off switches per source**
in Settings, **profile reuse** for unchanged documents, **ad texts reused for three days**,
**Adzuna's monthly allowance shared across the month**, **prompt caching** where a provider needs
asking, and `tools/coverage_test.py`.

**Real tests (the owner's own documents and keys, on a copy of his data folder):**
- *"Germany, but no cities where far-right parties polled above the national average, and only
  cities with at least 0.3% of the country's people", 24 hours*: 4 minutes, 268 ads, 251 different
  jobs, **139 left out by those conditions**, 56 shown. The far-right condition was researched live
  (Dresden, Chemnitz, Cottbus, Erfurt, Leipzig… excluded, sources: bundeswahlleiterin.de and
  others); the 0.3% condition was computed (at least 250,500 people in Germany, 15,930 in Ireland).
  Top results were real power-electronics jobs (Franka Robotics 96, GE Vernova 95, eMoSys 93).
- *Munich or within 50 km, 24 hours*: 19 ads, 9 scored, 2.5 minutes (before the new sources).
- *Ireland, 72 hours*: 94 seconds, no matching hardware jobs — his search words are narrow and
  Ireland has few such jobs that week.

**Waiting on the owner (Utku):**
1. **A friend is testing Jobcu.** Collect his feedback (installation, confusing steps, results).
2. **Run a real search yourself** and say whether the top results look right, whether any score is
   clearly wrong, and whether any title in "left out as clearly unrelated" was actually relevant.
   The new **Score check** screen is the place to record that: answer good / okay / poor for the
   jobs it kept from your searches.
3. Optional: a **generic cover letter** (the uploaded one is written for Tesla).
4. **A coverage list, to measure what Jobcu misses:** paste 15–25 jobs you'd want Jobcu to find
   (from LinkedIn, StepStone, Indeed, anywhere) into a text file, one per line:
   `Company | Job title | Place | link`. Then `uv run python tools/coverage_test.py that-file.txt`
   says how many Jobcu found and why it missed the rest. That's how we decide with numbers whether
   Jobcu needs the job boards that are on hold.
5. **Travel times need a Google Maps key** (your own choice earlier). Conditions like "at most 50
   minutes by public transport from a city centre" are answered as a clearly labelled **AI
   estimate** today. Real times need a Maps key with billing switched on, kept inside the free
   allowance. Say the word and I'll write the exact steps, one at a time.
6. **One question:** may facts that barely change (a town's population, the last election's
   results) be remembered with their source and date for a while, or should every search look them
   up again? Everything about the *jobs* stays fresh either way.
7. **Jooble and Careerjet** (aggregators covering Ireland, the UK and Germany) need free keys meant
   for websites showing their jobs, and Jobcu has no website. Your call whether to sign up.

**Countries:** 30 European countries (see `countries.py`). Search words use English plus the
languages of the places searched.
**Coverage goal:** as many jobs as possible across all 30, through every legally safe route.
Ireland, the UK and Germany are worked on and tested first.

**Next tasks for the assistant, in this order:**
1. **Use the score-check loop once the owner has answered a few jobs.** The screen and
   `tools/score_check.py` are built: the tool compares his answers with the scores Jobcu gave
   (free), or re-scores the same ads with different settings (`--rescore --batch 1 --effort medium
   --summary`) to tune the quick relevance check, batch size, summary vs full ad, reasoning effort,
   and how wide the search words should be (HANDOVER §13).
2. **More of Phase 2:** an Edit option for the interpretation, real travel times when the owner
   agrees to a Maps key, and remembering researched facts if he allows it.
3. **More coverage:** more employers in the directory, more career systems (SuccessFactors,
   Teamtailor, BambooHR, Comeet, Oracle), national public employment services with open APIs
   (Sweden's works and needs no key; Norway, France, Belgium and others need a free key or
   registration), and the decision about the job boards on hold once the coverage list exists.
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

- [ ] The AI splits the location text into conditions and picks a way to check each one
- [ ] **Live web search** for conditions that need facts (elections, shops, students, anything
      else), with the sources kept and shown
- [ ] **Real travel times** (Google Maps, weekday working hours, within the free allowance),
      one request per place and not per job
- [ ] Location interpretation shown with the results, with an Edit option, sources and clearly
      marked estimates
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
