# Jobcu progress

Where the project stands, and nothing else: git history says what was done, and
[DECISIONS.md](DECISIONS.md) says why. Kept current as described in [AGENTS.md](../AGENTS.md)
("Sessions").

## Right now

*Updated 2026-09-24. All 418 tests pass; GitHub's tests pass on macOS and Windows.*

### State

Jobcu works end to end. A search reads the documents with the person's own AI, collects jobs from
16 sources (8 of them company career systems, reading 357 employers), removes duplicates, applies
the rules and the location conditions, and scores what's left. The location box takes any
condition in the person's own words (sizes, facts the AI looks up per town, per region or per
country, travel limits to reference places), shows how each was checked, with sources, and can
be corrected with Edit. The owner has run four real searches on his Mac (2026-09-22/23); his
normal use will be one 24-hour search a day.

After search 8 (DECISIONS.md, 2026-09-23 evening and 2026-09-24): the AI reads the evidence in
each ad first and code applies the owner's limits for clear blockers; every summary-only job
scoring 50 or more is read online for its languages, years and town (asking before the web
look-ups run out); facts about places can be decided for whole regions; a reference place is
where the person would live, so a job in one needs no trip; every AI step thinks at medium, with
room for thinking on top of each answer. Adzuna stays as the biggest source, but Jobcu no longer
reads its pages (its firewall refuses them) and merges its "Deutschland" ads with the same job
elsewhere. Phase 1 waits only on the quality set the owner rates; most of Phase 2 is built.

### In progress

Nothing.

### Verify before relying on

- **Everything from 2026-09-23/24 inside one full search.** Each piece was checked live on its
  own (search 8's jobs, the owner's sentence, a second made-up sentence), never all together.
  On the next search check: German-required jobs stop at 65 with the reason on the card;
  "Languages and experience read from the full ad online" appears on summaries; Radeberg and
  Dresden stay out; a job inside a big city says "in Munich" rather than a drive to it; the
  question about more web look-ups appears if they run out.
- **Merging "Deutschland" ads with the same job elsewhere** (same company and title): search 8
  regrouped without a wrong merge seen, but a company with the same title in two towns could
  now show one card. Look for a card whose town doesn't match its ad.
- **The regions answer varies from search to search:** search 7 excluded Dresden, search 8's
  town list didn't, and three region answers on 2026-09-24 gave five or six eastern states.
  Compare the next searches' "Understood as".
- **Cost with medium everywhere:** estimated €0.45 for a 72-hour search like search 8, about a
  third of that for the usual 24-hour one (DECISIONS.md, 2026-09-24). Read the real figure in
  Settings → Usage after the next search.
- **Google Maps against the AI's estimates:** search 8 used Google's car times, but no one has
  compared them with the AI's estimates yet.
- **Towns found online:** search 8 found 44 of 53; the look-up is now two steps and asks for the
  place of the work, never an agency's office. Check a few "(found online)" towns. It has never
  run with another provider.
- **Teamtailor and SuccessFactors** were tested live source by source (2026-09-21), not yet
  confirmed inside a full search.
- **Maps billing SKU:** Billing → Reports should show only "Compute Route Matrix Essentials" at
  €0. Anything else means the limits need another look.
- **Caching under the EEA terms:** the storing rules in SOURCES.md come from the global Maps
  Service Specific Terms. Jobcu keeps nothing from Google, so this likely changes nothing; confirm
  in the EEA Service Specific Terms when touching `travel.py`.

### Waiting on the owner

1. **Restart Jobcu** (the one running was started before these changes), write his citizenship
   in "Anything your documents don't say", and **run a 24-hour search**. Then look at the items
   under "Verify" above.
2. **Rate 30–50 jobs on the Score check screen** (nothing is rated yet). Tuning the quick check
   and the scoring waits on this.
3. **A coverage list:** 15–25 jobs he'd want Jobcu to find, one per line as
   `Company | Job title | Place | link`, for `tools/coverage_test.py`.
4. **The friend's test:** his feedback on installing and using Jobcu.
5. Once the coverage numbers exist: keep the Stepstone Group boards on hold or ask them for
   permission ([SOURCES.md](SOURCES.md)), and whether to sign up for Jooble, Careerjet, France
   Travail, NAV or VDAB keys.

### Next tasks, in order

Tasks 2, 3 and 6 need nothing from the owner and can go ahead while he searches and rates.

1. **The owner's next search:** check it against "Verify" and fix what it shows.
2. **Phase 2's "Done when": every example sentence, checked live.** Run each sentence from
   HANDOVER §6, README.md and the owner's own through `location.interpret_location` with a real
   provider, twice, and fix what's misread in general terms, never for one sentence. One made-up
   sentence on 2026-09-24 found two general faults (a cut-off answer, fit and avoid swapped), so
   this is the cheapest way to find more. Done when every sentence reads as its author means,
   both times.
3. **Coverage beyond Adzuna, Germany, the UK and Ireland first.** Adzuna gives over half of the
   jobs, and only as summaries. Next: the career systems German small and mid-sized employers
   use (Personio, Softgarden), more Workday and SuccessFactors employers in German engineering,
   and Teamtailor employers in the UK and Ireland; then national services with open data for
   the other countries (Czechia's MPSV, Poland's CBOP, Finland, Estonia, Slovenia, Luxembourg).
   Check terms and robots.txt first and record each in SOURCES.md. Done when a search's unique
   jobs from sources with full ads grow, and the coverage test (task 4) shows the gaps.
4. **The coverage test** when the owner's list arrives (`tools/coverage_test.py`): which of his
   jobs Jobcu finds and why not; that decides the sources after task 3.
5. **The score check** when jobs are rated (`tools/score_check.py`): first the quick relevance
   check (it drops some related jobs in batches of similar ones, DECISIONS.md 2026-09-22
   evening; try one verdict per job or mixed batches), then medium against low thinking and the
   batch size for scoring, then the scoring prompt (HANDOVER §13). Done when the scores of 80%
   of rated jobs fall in the region the owner's answer expects.
6. **Ready for friends (Phase 4):** a first-run setup screen, updating from GitHub while keeping
   the data folder, the user guides tested on a clean Mac and a clean Windows computer, and the
   repository moved to a free GitHub organization, choosing with the owner how friends
   contribute.
7. **Cost, without losing quality (last, cost is fine now):** the scoring instructions and
   profile (about 3,000 tokens) go out with each of about 60 requests a search, and Gemini
   reported no cached tokens; try the provider's context caching (HANDOVER §13, saving 8).

### Known limitations

- The town list contains some city districts as separate places (Hamburg-Wandsbek, London's
  Brent). Harmless for conditions: they lie inside the bigger city.
- SuccessFactors sites whose job pages need JavaScript (Danfoss, SICK, Vitesco, Wacker) or
  redirect (MTU) aren't read, and pages opened for address-list sites aren't remembered between
  searches.
- Facts about places are looked up fresh in every search. Only the AI's travel estimates are
  remembered (30 days); Google's travel times may not be kept (Routes API terms).
- Adzuna's jobs are scored from ~500-character summaries (its pages refuse Jobcu); those
  scoring 50 or more are read online, and the rest keep the summary's evidence.
- A fact the AI can only answer per constituency ("Leipzig II") is kept as the AI wrote it; the
  town list doesn't know constituencies, so such an exception doesn't match its town. Edit fixes
  it ("Except Leipzig").

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
| 1. Usable first version | A real search with ranked, deduplicated results and reasons | 🔨 Real searches work; waiting on the quality set the owner rates |
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
- [x] **Done when:** the owner runs a real search on his Mac and gets a ranked, deduplicated list
      with reasons (2026-09-22 and 2026-09-23).

### Phase 2: Smart location filter

- [x] Conditions read from the person's own words; facts looked up on the web with sources; size
      rules; answers per town or per country
- [x] Travel limits to reference places: Google Maps with the person's key, otherwise AI estimates
- [x] "Understood as" with sources, labelled estimates and Edit
- [x] Facts decided per region
- [ ] Other reference data as needed (boundaries, coastlines, the UK
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
