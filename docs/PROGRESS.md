# Jobcu progress

Where the project stands, and nothing else: git history says what was done, and
[DECISIONS.md](DECISIONS.md) says why. Kept current as described in [AGENTS.md](../AGENTS.md)
("Sessions").

## Right now

*Updated 2026-09-24. All 500 tests pass; GitHub's tests pass on macOS and Windows.*

### State

Jobcu works end to end. A search reads the documents with the person's own AI, collects jobs from
25 sources (11 of them company career systems, reading 389 employers), lets the AI look at the
career-site titles the search words miss, removes duplicates, applies the rules and the location
conditions, and scores what's left with every AI step at **medium** effort (the owner's choice,
confirmed at the handover: DECISIONS.md, "Back to local sessions"). The location box takes any
condition in the person's own words, shows how each was checked, with sources, and can be
corrected with Edit. The owner has run nine real searches on his Mac (2026-09-22 to 24).

**Development is back in local Claude Code sessions on the owner's Mac** (final handover from
the cloud, 2026-09-24 night: the cloud credit is nearly used). Local sessions can use his real
data folder, with his permission, on a scratch copy (AGENTS.md, Commands), so everything the
cloud couldn't check can be checked now.

What the two cloud sessions did (2026-09-24; details in DECISIONS.md from "2026-09-24 (evening)"
on, and in SOURCES.md):
- **New sources:** service.bund.de, Teaching Vacancies, NHS Jobs, Le Forem, Werken voor
  Nederland, NAV, and the career systems prospective.ch, d.vinci and Eightfold; 389 employers in
  the directory (17 engineering employers added last, Moog, Microchip, Flex and Hitachi Energy
  among them).
- **Universal AI instructions** (`tools/universality_check.py`), robots.txt read as RFC 9309,
  closing dates and reposts on cards.
- **Search 9's findings (b) to (h) fixed**: trips to a reference place end at its nearest edge
  ("city centre" still means the centre) and a city's districts are part of it; UK postcodes,
  Eircodes, German state codes and English council districts are read; four kinds of duplicates
  merge; one question, in jobs, before more web look-ups, which also read citizenship, clearance
  and a doctorate; 3+ years short is limited to 80; `tools/coverage_test.py` says at which step
  each job was lost; Arbeitnow's escaped HTML is read.
- **Career-site titles the search words miss get a look from the AI** (2,377 fresh titles had
  been dropped unseen in one search); Workday stops on repeated pages; JobsIreland.ie's empty
  list is reported as a site problem.
- Two 72-hour searches with the owner's CV in the cloud (no Adzuna, Reed or Google key there,
  low effort because of the cloud's 30-second limit): **171 cards instead of 86, 21 in Ireland
  instead of 2**, the best a graduate programme in electrical engineering in Cork.
- Tried and not shipped: the AI searching the web for single jobs (task 3).

What the cloud could **not** check, so the next search on the Mac shows it for the first time:
anything with Adzuna, Reed or Google Maps (the travel edge rule with real routes, Reed's
postcodes, Adzuna summaries read online with the new citizenship limits), web research at medium
effort (the location research and the online look-up), the AI's look at career-site titles at
medium, and what all this costs now that more jobs reach scoring.

### In progress

Nothing.

### Verify before relying on

- **The next search on the Mac** (the first with everything above), through its local check:
  the "Searching job sources" step says how many career-site titles the AI looked at and kept;
  graduate programmes and titles like "RF Power Amplifier Design" reach the cards; trips to the
  nearest edge with Google Maps (jobs like Weichs, Weßling and Potsdam pass, nothing far away
  passes wrongly); Reed postcodes read as towns and merged; council districts applied; one
  question for more web look-ups, with its time; citizenship and clearance limits from the online
  look-up; no wrong merges of summaries; senior roles asking 3–4 more years at most 80; **the
  cost and the time**.
- **The robots.txt reader** (RFC 9309): check at the next `tools/check_employers.py` run that no
  newly read company clearly forbids it.
- **Sources not seen inside a search yet:** "apply by …" on a card, and Le Forem, prospective.ch,
  Werken voor Nederland, NAV and d.vinci in searches of their countries.
- **The regions answer varies from search to search** (Dresden in or out, Wales, Ashfield):
  compare the next searches' "Understood as".
- **Cost:** search 9 (72 hours, medium) was about $1.36 at $0.75/$3.75 per million tokens: one
  24-hour search a day is about $14 a month now and about $27 after the prices double on
  1 January 2027, above the €23 AI budget. More jobs reach scoring now. Savings may never come
  from a lower effort (the owner) or from fewer fresh jobs (AGENTS.md): see task 2.
- **Google Maps:** Billing → Reports should show only "Compute Route Matrix Essentials" at €0;
  no comparison of Google's times with the AI's estimates yet; the EEA terms for storing
  (SOURCES.md) to confirm when touching `travel.py`.
- **Towns found online:** search 9 found 17 of 41 (search 8: 44 of 53); never run with another
  provider.

### Waiting on the owner

1. **The next search:** restart Jobcu with the launcher (it updates itself from GitHub first)
   and run a **72-hour search** with his usual sentence; then a local session with the prompt
   "Check my latest search" (CONTRIBUTING.md). After that, a 72-hour search every two or three
   days while Jobcu is developed.
2. **So that Settings → Usage shows what each search costs:** enter the model's prices there
   ($0.75 input and $3.75 output per million tokens until 31 December 2026).
3. **The friend's test:** his feedback on installing and using Jobcu.
4. **Only if he wants to send them** (messages in his name): access requests to StepStone,
   Denmark's Jobnet, Poland's CBOP, or a private NAV token. None is needed for the current focus.

The quality set and the coverage list are made by the local check on his behalf (DECISIONS.md,
2026-09-24 night); he may still rate or add jobs himself.

### Next tasks, in order

**The mission** (the owner, 2026-09-24): the best job search app possible, **universal** (any
profession, any of the 30 countries, any wording), clean, reliable and without errors. The
sessions decide everything (DECISIONS.md, 2026-09-24 evening); what costs money, touches his
accounts or needs a message in his name stays his. **The owner's priorities** (DECISIONS.md, "The
owner's priorities"): **Germany first, then the UK and Ireland**, no more sources for other
countries until these three are as strong as possible; test first and most with **a graduate
engineer in electronics and power electronics hardware**; **his own searches are the real test**
and their findings come before everything else. **Every AI step stays at medium effort.** Cost:
at most €25 a month for the owner; free, or under €10 a month, for everyone else.

1. **Check the next search** ("Check my latest search"): everything under "Verify before relying
   on", the ratings and the coverage list; record the findings here and fix them first. Still
   open from search 9: (a) jobs never collected, above all agencies seen only on LinkedIn and
   StepStone (tasks 3 and 4) and employers missing from the directory (task 5); (f) neighbouring
   fields scoring too high (analog chip design 71, PLC commissioning 70) and the quick check
   leaving out 2 of 39 titles worth a look.
2. **Cost at medium effort:** measure the next search's cost per step (Settings → Usage, "Search
   details"). If the monthly cost goes above the budget, save where it loses nothing: score only
   what the quick check keeps, send the scoring instructions and profile once per search with
   the provider's context caching (about 3,000 tokens with each of about 60 requests; HANDOVER
   §13, saving 8), and try the batch size with `tools/score_check.py`. Never a lower effort.
3. **The AI finds employers, not jobs** (the route after the single-job experiment, DECISIONS.md
   "The person's AI searching the web for single jobs"): the AI looks up employers hiring for the
   person's kind of work in the places searched, with their career-site address; Jobcu recognises
   the career system from that address (Workday, Greenhouse, Lever, Teamtailor, d.vinci…),
   checks it with one request and reads its jobs like the directory's, remembering the employers
   found for later searches.
4. **Fewer jobs depending on Adzuna's summaries:** find the same job at its original (the
   employer's career site, the Bundesagentur) before reading it online, and measure how many
   still rely on a summary.
5. **More employer career sites in Germany, the UK and Ireland**, measured with whole searches
   (`tools/made_up_search.py` and the owner's own): (a) the real Workday addresses of the 30
   employers whose guessed sites answered 422 (AMD, Dell, Keysight, onsemi, TE Connectivity,
   Honeywell, Schneider Electric, Zeiss, Continental…; SOURCES.md), then
   `tools/check_employers.py --only-new --write`; (b) **Personio** and **softgarden** career pages
   (check terms, robots.txt and JobPosting first) and **Avature** (Siemens, Siemens Energy);
   (c) more employers on the systems Jobcu reads: semiconductors, power electronics, automotive
   and industrial electronics, drives, defence, medical devices, test and measurement, energy
   (Rohde & Schwarz, Renesas, Arm, Bosch seen; SOURCES.md); (d) whether the robots fix lets more
   Workday and SuccessFactors companies through, and Micron's Eightfold site.
6. **Phase 2's "Done when":** every example sentence from HANDOVER §6, README.md and the owner's
   own, read twice with a real provider, as its author means it. Fix in general terms, never for
   one sentence.
7. **Scoring with the quality set** (`tools/score_check.py`, on his Mac): the quick check first,
   then the scoring prompt (HANDOVER §13), once the set holds good fits too.
8. **Paused until Germany, the UK and Ireland are as strong as possible:** sources for other
   countries (SOURCES.md), the licence limit for other professions, and the universality audit's
   rest (re-run `tools/universality_check.py` after any change to the AI instructions, which
   stays a rule).
9. **Ready for friends (Phase 4):** a first-run setup screen, updating from GitHub while keeping
   the data folder, the guides tested on a clean Mac and a clean Windows computer, and the
   repository moved to a free GitHub organization, choosing with the owner how friends
   contribute.

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
| 1. Usable first version | A real search with ranked, deduplicated results and reasons | 🔨 Real searches work; the first quality set is rated, the scoring prompt not tuned yet |
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
- [ ] A quality set of 30–50 real ads judged for the owner (the Score check screen collects them;
      32 ads and 39 titles rated by Claude on 2026-09-24, none of the ads a good fit yet) and a
      tuned scoring prompt (HANDOVER §13)
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

- [x] 25 sources: Adzuna, Reed, Bundesagentur für Arbeit, service.bund.de, JobsIreland.ie,
      jobs.ac.uk, Teaching Vacancies, NHS Jobs, Le Forem, Werken voor Nederland, NAV,
      EURAXESS, Arbeitnow, Arbetsförmedlingen, and company career sites in 11 systems
      (Greenhouse, Lever, Ashby, Workable, Recruitee, Workday, Teamtailor, SuccessFactors,
      prospective.ch, d.vinci, Eightfold) for 389 employers
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
