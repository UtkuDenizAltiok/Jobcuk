# Jobcu progress

Where the project stands, and nothing else: git history says what was done, and
[DECISIONS.md](DECISIONS.md) says why. Kept current as described in [AGENTS.md](../AGENTS.md)
("Sessions").

## Right now

*Updated 2026-09-22. All 372 tests pass; GitHub's tests pass on macOS and Windows.*

### State

Jobcu works end to end. A search reads the documents with the person's own AI, collects jobs from
16 sources (8 of them company career systems, reading 357 employers), removes duplicates, applies
the rules and the location conditions, and scores what's left. The location box takes any
condition in the person's own words (sizes, facts the AI looks up per town or per country, travel
limits to reference places), shows how each was checked, with sources, and can be corrected with
Edit. Phase 1 waits only on the owner's own real search; most of Phase 2 is built.

### In progress

Nothing.

### Verify before relying on

- **Google Maps has only met a fake Google in tests.** Once the owner's key is saved: press Test
  in Settings, then run one real search with a travel limit and compare Google's times with the
  AI's estimates.
- **Teamtailor and SuccessFactors** were tested live source by source (2026-09-21), not yet inside
  a full search.
- **Maps billing SKU:** after the first real searches, Billing → Reports should show only
  "Compute Route Matrix Essentials" at €0. Anything else means the limits need another look.
- **Google's daily quota has never been reached.** When it is, Google presumably answers 429 and
  Jobcu falls back to AI estimates with "asked Jobcu to slow down"; check the wording then.
- **Caching under the EEA terms:** the storing rules in SOURCES.md come from the global Maps
  Service Specific Terms. Jobcu keeps nothing from Google, so this likely changes nothing; confirm
  in the EEA Service Specific Terms when touching `travel.py`.

### Waiting on the owner

1. **Google Maps key, last step:** copy "Jobcu Google Maps key" (Credentials → Show key) into
   Jobcu's Settings → Travel times → Save → Test Google Maps. Everything else on Google's side is
   set up (DECISIONS.md, "The owner's Google billing"). His Gemini key ("Jobcu AI key") is
   already saved in Jobcu.
2. **Run a real search** and rate a few jobs on the Score check screen (nothing is rated yet).
3. **A coverage list:** 15–25 jobs he'd want Jobcu to find, one per line as
   `Company | Job title | Place | link`, for `tools/coverage_test.py`.
4. **The friend's test:** his feedback on installing and using Jobcu.
5. Optional: a generic cover letter (the uploaded one is written for Tesla).
6. Once the coverage numbers exist: keep the Stepstone Group boards on hold or ask them for
   permission ([SOURCES.md](SOURCES.md)), and whether to sign up for Jooble, Careerjet, France
   Travail, NAV or VDAB keys.

### Next tasks, in order

1. Once the owner has saved the Maps key: press Test, then one real search with a travel limit,
   comparing Google's times with the AI's estimates (the first item under "Verify").
2. Once jobs are rated: try scoring at **medium** thinking too (the owner leans to medium for
   every step, 2026-09-22; decide with the score check, not before). Then the score-check loop (`tools/score_check.py` to compare; `--rescore` to
   tune the quick check, batch size and scoring prompt, HANDOVER §13).
3. More coverage, Ireland, the UK and Germany first: Teamtailor employers in Ireland and the UK,
   SuccessFactors sites of German engineering firms, more career systems (Personio, Softgarden,
   BambooHR, Comeet, Oracle), and national employment services with open data and no key
   (candidates: Czechia's MPSV open data, Poland's CBOP, Finland, Estonia, Slovenia, Luxembourg).
   Check terms and robots.txt first; record each in SOURCES.md.
4. The rest of Phase 2: facts decided per region (needs region names in the town list,
   `tools/update_places.py` with GeoNames admin1 codes), and kinds of places near the job itself
   (a train station) if the owner wants them.
5. Keep the user guides in step, fix what the tester reports, and confirm Phase 1's "Done when"
   with the owner.

### Known limitations

- The town list contains some city districts as separate places (Hamburg-Wandsbek, London's
  Brent). Harmless for conditions: they lie inside the bigger city.
- SuccessFactors sites whose job pages need JavaScript (Danfoss, SICK, Vitesco, Wacker) or
  redirect (MTU) aren't read, and pages opened for address-list sites aren't remembered between
  searches.
- Facts about places are looked up fresh in every search. Only the AI's travel estimates are
  remembered (30 days); Google's travel times may not be kept (Routes API terms).

## Owner's setup and reference numbers

- Data folder `~/Library/Application Support/Jobcu`, with the keys `adzuna_app_id`,
  `adzuna_app_key`, `ai_gemini` and `reed_api_key` (`google_maps` once set up). AI: Google Gemini,
  model `gemini-3.8-flash`, paid (€15 in advance), with Google's spend cap at €23 a month on the
  project "Jobcu AI" (everything together never above €25); web search works on it.
- Real tests only on a copy of that folder, deleted afterwards (AGENTS.md, Commands).
- A German 24-hour search takes about 4 minutes (Workday is the slowest source: about 400
  requests when no place is named); Munich or within 40 km over 72 hours about 3 minutes.
  Re-checking the whole employer directory takes about 15 minutes; `--only-new` for new
  candidates under a minute.

## Milestones

| Phase | What it delivers | Status |
|---|---|---|
| 0. Foundations | Project set-up; Jobcu starts with a double-click | ✅ Done (2026-09-17) |
| 1. Usable first version | A real search with ranked, deduplicated results and reasons | 🔨 Built; waiting on the owner's real search and the quality set |
| 2. Smart location filter | Understands sentences like "a city by the seaside" | 🔨 Mostly built |
| 3. Maximum coverage | Many more job sources in every supported country | 🔨 Started |
| 4. Ready for friends | Complete guides, first-run setup, tested on real Mac and Windows computers | Planned |

### Phase 1: Usable first version

- [x] AI provider layer (Anthropic, Google Gemini, OpenAI, any OpenAI-compatible provider) and a
      Settings screen with keys, connection tests, usage meter, monthly limits, prices and source
      switches
- [x] CV and cover letter reading, with "What Jobcu understood"; the profile is reused while the
      documents are unchanged
- [x] Search screen with progress and Search details; hidden multilingual search words
- [x] Time, job type and remote filters; duplicates with the employer's page as main link; quick
      relevance check; scoring with reasons; a scoring limit that asks before doing more
- [x] Results: Save, Applied, Not interested, "New", Saved and Applied lists, sorting, "Posting
      date unknown"
- [ ] A quality set of 30–50 real ads judged by the owner (the Score check screen collects them)
      and a tuned scoring prompt (HANDOVER §13)
- [ ] **Done when:** the owner runs a real search on his Mac and gets a ranked, deduplicated list
      with reasons.

### Phase 2: Smart location filter

- [x] Conditions read from the person's own words; facts looked up on the web with sources; size
      rules; answers per town or per country
- [x] Travel limits to reference places: Google Maps with the person's key, otherwise AI estimates
- [x] "Understood as" with sources, labelled estimates and Edit
- [ ] Facts decided per region; other reference data as needed (boundaries, coastlines, the UK
      sponsor register)
- [ ] **Done when:** the example sentences in HANDOVER §6, in README.md and the owner's own
      examples behave as described, each with its working shown.

### Phase 3: Maximum coverage

- [x] 16 sources: Adzuna, Reed, Bundesagentur für Arbeit, JobsIreland.ie, jobs.ac.uk, EURAXESS,
      Arbeitnow, Arbetsförmedlingen, and company career sites in 8 systems (Greenhouse, Lever,
      Ashby, Workable, Recruitee, Workday, Teamtailor, SuccessFactors) for 357 employers
- [x] Per-source status, unique-job counts and on/off switches
- [ ] A source for every supported country (HANDOVER §9.0)
- [ ] More career systems and employers; live AI web search for jobs (HANDOVER §9.6)
- [ ] **Done when:** the coverage test shows no large avoidable gaps, and the remaining gaps are
      explained to the owner.

### Phase 4: Ready for friends

- [ ] Full manual test on a real Windows computer and a real Mac
- [ ] Complete everyday-user guides (HANDOVER §2.1), tested on clean computers
- [ ] First-run setup screen and polished double-click launchers
- [ ] Updating from GitHub while keeping the data folder
- [ ] Move the repository to a free GitHub organization and invite friends, choosing with the owner
      how friends can contribute (see DECISIONS.md)
