# Jobcu progress

Where the project stands, and nothing else: git history says what was done, and
[DECISIONS.md](DECISIONS.md) says why. Kept current as described in [AGENTS.md](../AGENTS.md)
("Sessions").

## Right now

*Updated 2026-09-24. All 483 tests pass; GitHub's tests pass on macOS and Windows.*

### State

Jobcu works end to end. A search reads the documents with the person's own AI, collects jobs from
25 sources (11 of them company career systems, reading 372 employers), removes duplicates, applies
the rules and the location conditions, and scores what's left. The location box takes any
condition in the person's own words (sizes, facts the AI looks up per town, per region or per
country, travel limits to reference places), shows how each was checked, with sources, and can
be corrected with Edit. The owner has run five real searches on his Mac (2026-09-22 to 24); his
normal use will be one 24-hour search a day.

After search 8 (DECISIONS.md, 2026-09-23 evening and 2026-09-24): the AI reads the evidence in
each ad first and code applies the owner's limits for clear blockers; every summary-only job
scoring 50 or more is read online for its languages, years and town (asking before the web
look-ups run out); facts about places can be decided for whole regions; a reference place is
where the person would live, so a job in one needs no trip; every AI step thinks at medium, with
room for thinking on top of each answer. Adzuna stays as the biggest source, but Jobcu no longer
reads its pages (its firewall refuses them) and merges its "Deutschland" ads with the same job
elsewhere. Phase 1 waits only on tuning the scoring with the quality set; most of Phase 2 is built.

The first cloud session (2026-09-24) researched sources per country (SOURCES.md, "Candidate sources
by country") and built public-sector and national sources (service.bund.de, Teaching Vacancies, NHS
Jobs, Le Forem, Werken voor Nederland, NAV) and career systems (prospective.ch, d.vinci, Eightfold
with Infineon, Qualcomm, Ericsson and Vodafone). Cards show closing dates and reposts. The AI
instructions were made universal (`tools/universality_check.py`), which fixed a language bug that
capped good jobs at 65 for anyone with a CV not in English. robots.txt is now read as the standard
says. Then the owner set the priorities (DECISIONS.md, "The owner's priorities"): Germany, the UK
and Ireland, and a graduate power-electronics engineer first; `tools/made_up_search.py` measures a
whole search for such a person, and showed that the directory's career sites still find almost
nothing for him.

From 2026-09-24 development runs in Claude Code cloud sessions (AGENTS.md, "Working in a cloud
session"): no access to the owner's data there, so his searches and ratings come back as his
reports, or through a local session on his Mac.

**The owner's search 9** (2026-09-24, DE/IE/GB, 72 hours, his far-right and 40-minutes-by-car
sentence; studied in a local session the same evening): it ran end to end without errors, but
took **33 minutes** (scoring 8, the online look-up 12) and cost about **$1.36** at today's Gemini
prices (search 8: $0.54). 890 ads, 774 jobs, 239 cards: 132 in Germany, 105 in the UK, **2 in
Ireland**. Adzuna 443 ads (121 unique), the Bundesagentur 171 (53), Reed 155 (38), jobs.ac.uk 72,
the career sites 15 (Workday 11 from 734 requests). The first **quality set** is rated (32 ads and
39 left-out titles, by Claude) and the first **coverage list** (25 fresh jobs from LinkedIn and
StepStone) was tested: Jobcu showed **3 of 25**, and 20 were never collected by any source. The
findings, with examples, are Next task 1.

### In progress

Nothing.

### Verify before relying on

- **The robots.txt reader** (RFC 9309, 2026-09-24): Workday and SuccessFactors companies now
  read differently where their robots.txt has Allow lines after a Disallow. Check that no
  company newly read is one that clearly forbids it (the next `tools/check_employers.py` run).
- **The new sources inside a full search** (2026-09-24): search 9 showed service.bund.de,
  Teaching Vacancies and NHS Jobs in Search details with their counts, without slowing the search
  (service.bund.de: 1 request, 0 jobs, "reaches back only to 22 September"). "First seen by Jobcu
  on …" is right (12 cards, all Adzuna reposts). Still unseen: "apply by …" on a card (1 of 239 had
  a closing date) and the non-German sources (Le Forem, prospective.ch, Werken voor Nederland,
  NAV, d.vinci) inside a search of their countries.
- **Merging "Deutschland" ads with the same job elsewhere:** no wrong merge seen in search 9
  (not checked card by card). The opposite fault is common (Next task 1e).
- **The regions answer varies from search to search:** search 7 excluded Dresden, search 8's
  town list didn't; search 9 gave Brandenburg, Mecklenburg-Vorpommern, Saxony, Saxony-Anhalt,
  Thuringia and Wales, except Potsdam and Cardiff. Compare the next searches' "Understood as".
- **Cost with medium everywhere:** search 9 (72 hours) came to about $1.36 at $0.75/$3.75 per
  million tokens (SOURCES.md, Gemini): 398k input, 282k output tokens, of which 199k thinking,
  and 200 web searches (within Gemini's 5,000 free a month). One 24-hour search a day at that rate
  is about $14 a month now, about $27 after the prices double on 1 January 2027, which is above
  the €23 AI budget. Jobcu shows no cost because no prices are entered in Settings.
- **Google Maps against the AI's estimates:** search 9 measured every trip with Google (88 cards)
  or by distance; still no comparison with the AI's estimates.
- **Towns found online:** search 9 found 17 of 41 (search 8: 44 of 53). The ones checked look
  right (Leonardo in Edinburgh, Helmut-Schmidt-Universität in Hamburg, iCuTech in Lauf an der
  Pegnitz, Ralliant in Bracknell). It has never run with another provider.
- **Maps billing SKU:** Billing → Reports should show only "Compute Route Matrix Essentials" at
  €0. Anything else means the limits need another look.
- **Caching under the EEA terms:** the storing rules in SOURCES.md come from the global Maps
  Service Specific Terms. Jobcu keeps nothing from Google, so this likely changes nothing; confirm
  in the EEA Service Specific Terms when touching `travel.py`.

### Waiting on the owner

1. **The cloud credit:** he watches it at claude.ai, Settings → Usage, and sends the
   final-handover prompt (CONTRIBUTING.md) at about $85 used. (Cloud setup works: checked
   2026-09-24, with Full network access and the Gemini credential answering.)
2. **Searches while Jobcu is developed:** close Jobcu and start it again with the launcher (it
   now updates itself from GitHub first) and run a **72-hour search every two or three days**. After each, a short local
   session with the prompt "Check my latest search" (CONTRIBUTING.md) records what it shows for
   the cloud sessions. Screenshots in the cloud chat are fine for anything that looks wrong.
3. Nothing to rate or list by hand: the owner handed the quality set (30–50 rated ads) and the
   coverage list (15–25 jobs he'd want) to the local check, Prompt D in CONTRIBUTING.md
   (DECISIONS.md, 2026-09-24).
4. **The friend's test:** his feedback on installing and using Jobcu.
5. **So that Settings → Usage shows what each search costs:** enter the model's prices there
   ($0.75 input and $3.75 output per million tokens until 31 December 2026). Without them Jobcu
   shows tokens only.
6. **Only if he wants to send them** (messages in his name; DECISIONS.md, 2026-09-24 evening):
   access requests to StepStone, Denmark's Jobnet, Poland's CBOP, or a private NAV token. None
   is needed for the current focus.

### Next tasks, in order

**The mission** (the owner, 2026-09-24): the best job search app possible, **universal** (any
profession, any of the 30 countries, any wording), clean, reliable and without errors. The
sessions decide everything (DECISIONS.md, 2026-09-24 evening); what costs money, touches his
accounts or needs a message in his name stays his. **The owner's priorities** (2026-09-24,
DECISIONS.md "The owner's priorities"): **Germany first, then the UK and Ireland**, and no more
sources for other countries until these three are as strong as possible; test first and most
with **a graduate engineer in electronics and power electronics hardware**, so that Jobcu finds
and ranks technical and engineering jobs there as well as possible; **his own searches are the
real test**, and their findings (from a local session on his Mac) come before everything else.
Cost: at most €25 a month for the owner; free, or under €10 a month, for everyone else. Findings
go to their homes: source facts to SOURCES.md, choices and reasons to DECISIONS.md, the plan
here.

1. **Findings from the owner's own searches**, whenever a local session records them here: they
   come before everything else. **From search 9** (local check, 2026-09-24), most important first:
   (a) **Sources miss most fresh jobs.** Of 25 fresh jobs that fit his CV (LinkedIn and StepStone,
   posted within the window), Jobcu showed 3 (Amadeus Fire in Hanover, Jobactive in Bremen, Össur
   in Livingston as "Embla Medical"), 2 were collected and rightly left out by his conditions
   (Great Yarmouth, Bridgend), and **20 were never collected**: all 5 in Ireland (Moog and
   Advanced Energy in Cork, Stryker's "RF Power Engineer - R&D" in Cork, Ei Electronics in
   Shannon), employers not in the directory (Nordex in Hamburg, Tektronix in Viersen, Saab in
   Nuremberg, Bosch in Renningen, Luxinar in Krailling, Cambridge Consultants, ASSA ABLOY, Zenovo
   in Derby) and agencies seen only on LinkedIn or StepStone (HILL, Next Ventures, XTENDED,
   Actana, IC Resources' graduate job in Cambridge). Search 9 had only 2 Irish cards. So task 2
   (the directory: Moog runs Workday; the others' systems are in SOURCES.md) and task 3 (the AI
   searching the web) matter most, with Ireland first among the two.
   (b) **Travel limits measured to a city's centre leave jobs out wrongly.** Google gave Weichs →
   Munich 53 minutes (Munich's centre), so three PCB-layout jobs in Weichs were left out at
   "Augsburg, 50 min"; Forchheim → Nuremberg 44, Schrobenhausen → Augsburg 41. A reference place
   is where the person would live (DECISIONS.md, 2026-09-24), so measure to the nearest part of
   the city, not its centre. City districts that are reference places on their own (Hamburg's
   Wandsbek, Eimsbüttel, and "Marienthal" with 287,101 people) take both "nearest" slots and
   appear on cards ("Marienthal, 53 min by car").
   (c) **Done (cloud, 2026-09-24): postcodes, state codes and council districts are read**
   (DECISIONS.md, "Places Jobcu couldn't read in search 9"); check them in the next search.
   What search 9 showed: **Place names the town list can't read.** Reed gives full UK postcodes as the place
   ("CB224QR", "S336RR": 7 cards "couldn't be checked"); the Bundesagentur sometimes gives a state
   code, shown raw ("BADEN_WUERTTEMBERG"); and 6 of the 32 UK names to avoid were council
   districts that match no town (Thanet, Thurrock, Castle Point, Ashfield, Amber Valley, Cannock
   Chase), so those areas passed without a word. Read postcodes and state codes, and look
   unmatched names up among the regions and districts (`regions.csv.gz`).
   (d) **The online look-up asks too often and reads too little.** The question about more web
   look-ups came about four times in search 9; the owner said yes to all but the last (his
   answer, 2026-09-24), which fits the 200 web searches exactly (50, then three more
   allowances). Each "yes" read fewer jobs than he expected: the question counts web look-ups
   (50) while its button counts jobs, and each job takes about two look-ups, so one allowance
   reads about 25 jobs. Ask once, in jobs, for everything left (with a rough cost), and size the
   allowance by jobs, not searches. Of the jobs it asked about it found most (requirements for 85
   of 130 needing them, towns for 17 of 41); the rest were never asked because the owner stopped,
   so 44 summary cards scoring 50+ kept their summary, and JAT in Jena (a region he excludes)
   stayed at 81 without its town. It reads only languages and years: Rolls-Royce's two Adzuna
   summaries scored 85 and 75, while the same jobs from its own Workday site say UK nationals
   only (30). Read citizenship and clearance (and a required doctorate) too. It took 12 minutes.
   (e) **Four pairs of the same job shown twice** (the postcode and "Heeley, Sheffield" pairs
   fixed 2026-09-24; the two summaries and "Rolls-Royce (professional)" still open), each for a
   different reason: Reed's postcode
   ("BB113BP") against Adzuna's "Burnley, Lancashire" (Corriculo, 88 and 82); two Adzuna
   summaries of a recruiter's ad, which must be full ads to merge (AMF in Castleford, 87 twice);
   "Heeley, Sheffield" against "Sheffield" (Adecco); and the directory's company name "Rolls-Royce
   (professional)" with no town. Summaries could merge when one's text is contained in the
   other's (`_text_similarity` already measures containment).
   (f) **Scoring** (score check, 32 ads rated by Claude): 23 of 32 (72%) where expected with the
   scores given at the time, **26 of 32 (81%) re-scored with today's code** (the owner's limits
   now hold 8+ and 10+ years to 60). Still too high: senior jobs asking 4–7 years for someone with
   no full-time years (Tactilia 68, Stark 68, Orbem 64) and neighbouring fields (analog chip design
   71, PLC commissioning 70). The quick check left out 2 of 39 titles worth a look (a university
   lab lead for electric drives, a quality engineer at a hardware company). No ad in the set is a
   good fit yet, so the check can't tell whether good jobs score high enough.
   (g) **`tools/coverage_test.py` gives wrong reasons:** it looks only at the cards, so a job that
   was never collected is blamed on the quick check or the search words, and a different job of
   the same company counts as found (Zenovo's Bristol test job for its Derby one). It should look
   in the saved pool (every job collected) and say at which step each was lost, match titles
   more strictly, and accept a company's other name (Össur and Embla Medical).
   (h) Small: Arbeitnow sometimes sends escaped HTML, so the ad text keeps literal tags
   (SOURCES.md, Arbeitnow).
   (i) **Cost and time:** 33 minutes and about $1.36 for 72 hours; 70% of the output tokens were
   thinking. Before prices double in January, find where lower thinking keeps the same answers
   (task 7's order).
2. **More employer career sites of engineering and tech companies in Germany, the UK and
   Ireland.** The first full cloud searches (DECISIONS.md, 2026-09-24 evening) found no job at
   all through the directory's career sites for a hardware engineer around Munich or in Dublin.
   **Measure every step** with `tools/made_up_search.py` (the made-up graduate
   power-electronics engineer; its own data folder), over **72 hours** too: 24 hours is too
   narrow to tell sources apart. Baseline (2026-09-24, 24 hours, "Munich or within 40 km, or
   Dublin", no Adzuna key in the cloud): 5 jobs shown before Eightfold, 7 after; career sites 0
   both times. In order:
   (a) Done 2026-09-24: **Eightfold** (Infineon, Qualcomm, Ericsson, Vodafone) and robots.txt
   read as RFC 9309. Next: find out whether the robots fix now lets more Workday and
   SuccessFactors companies through (compare `tools/check_employers.py` before and after), and
   add Micron's Eightfold site if its Workday list is gone.
   (b) **Personio** and **softgarden** career pages (many German engineering SMEs; check terms,
   robots.txt and JobPosting first), and **Avature** (Siemens, Siemens Energy).
   (c) More employers on the systems Jobcu reads (Workday, SuccessFactors, Teamtailor,
   Greenhouse, d.vinci, Eightfold): semiconductors, power electronics, automotive and industrial
   electronics, drives, defence, medical devices, test and measurement, energy; Germany first,
   then the UK and Ireland (Cork, Limerick, Galway, Dublin; Cambridge, Bristol, Manchester…).
   Candidates already seen: Rohde & Schwarz, Renesas, Arm, Bosch (SOURCES.md, career systems).
3. **The best legal routes to the jobs on LinkedIn and StepStone:** the person's AI searches the
   web for fresh jobs (HANDOVER §9.6), and each is shown once Jobcu confirms it at a source it
   may read, above all the employer's own career page (DECISIONS.md, 2026-09-24 evening).
4. **Fewer jobs depending on Adzuna's summaries:** find the same job at its original (the
   employer's career site, the Bundesagentur) before reading it online, and measure how many
   Adzuna jobs still rely on a summary after steps 2 and 3.
5. **Paused until Germany, the UK and Ireland are as strong as possible:** sources for other
   countries (the research is in SOURCES.md; Belgium's school jobs, more d.vinci and
   prospective.ch employers), the licence limit for other professions, and the universality
   audit's rest (re-run `tools/universality_check.py` after any change to the AI instructions,
   which stays a rule).
6. **Phase 2's "Done when":** every example sentence from HANDOVER §6, README.md and the owner's
   own, read twice with a real provider, as its author means it. Fix in general terms, never for
   one sentence.
7. **The owner's feedback loop:** fix what his searches show; with the ratings (32 ads and 39
   titles, rated by Claude on his behalf since 2026-09-24), the score check (`tools/score_check.py`,
   on his Mac): the quick check first, then medium against low thinking and the batch size, then
   the scoring prompt (HANDOVER §13); the coverage test with each local check's new list. Consider a way for him to share a search's results with a cloud
   session without personal data (no CV, no profile).
8. **Ready for friends (Phase 4):** a first-run setup screen, updating from GitHub while keeping
   the data folder, the guides tested on a clean Mac and a clean Windows computer, and the
   repository moved to a free GitHub organization, choosing with the owner how friends
   contribute.
9. **Cost, last:** the scoring instructions and profile (about 3,000 tokens) go out with each of
   about 60 requests a search; try the provider's context caching (HANDOVER §13, saving 8).

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
      prospective.ch, d.vinci, Eightfold) for 372 employers
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
