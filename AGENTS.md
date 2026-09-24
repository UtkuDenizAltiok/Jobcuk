# Jobcu: the rulebook for AI assistants and developers

This file is for **anyone working on Jobcu**, with or without an AI assistant (Claude, ChatGPT or
Codex, Gemini, Grok, Kimi, Cursor, Copilot, Aider…). Many AI tools load it by themselves; if yours
doesn't, read all of it before doing anything. It is the only rulebook: where it and another
document disagree, fix the other document. People start with [CONTRIBUTING.md](CONTRIBUTING.md),
which also has ready-made prompts for AI assistants.

## What Jobcu is

Jobcu is a private job search app for 30 European countries (see `countries.py`). It runs on the
user's own Mac or Windows computer and is used through a browser. The user gives it a CV, a cover
letter and a free-text description of where they want to work. On **Search**, it collects fresh
job ads from as many sources as possible, removes duplicates, applies the location criteria,
scores each job against the user's profile with an AI model the user chose, and shows a ranked
list with short reasons.

**Jobcu is universal.** It is for anyone: any profession (engineers, teachers, nurses, chefs,
lawyers, drivers…), any of the 30 countries, any way of writing, any AI provider. The owner is
one user, not the target: never tune prompts, examples, data, sources or defaults to his profile
or his searches; that is why the person's own AI reads everything. Examples in AI instructions
come from several professions and countries, and every change to how Jobcu reads people, places
or ads is tried with made-up people from other fields (a primary-school teacher in Ghent, an ICU
nurse in Cork, a sous-chef in Zürich) as well as with the owner's own words.

**Where the work goes first** (the owner, 2026-09-24, DECISIONS.md): **Germany first, then the
UK and Ireland**; no more sources for other countries until these three are as strong as
possible. Jobcu stays universal, but it is **tested first and most with a graduate engineer in
electronics and power electronics hardware**: what matters most now is that Jobcu finds and
ranks technical and engineering jobs in these three countries as well as possible (more
employer career sites of engineering and tech companies, the best legal routes to the jobs on
LinkedIn and StepStone, fewer jobs depending on Adzuna's summaries). **The owner's own searches
are the real test**: findings from them arrive in PROGRESS.md from a local session on his Mac
and come before everything else. That is an order of effort, not a design rule: nothing is
tuned to the owner's own profile, and nothing may break other kinds of work.

## Where everything lives

Every kind of information has exactly one home. Record it there once and link to it elsewhere;
never copy it into a second place.

| Information | Its home |
|---|---|
| How to work on Jobcu: rules, architecture, conventions, session routine, lessons | this file |
| Where the project stands: state, work in progress, things to verify, what waits on the owner, next tasks, milestones | [docs/PROGRESS.md](docs/PROGRESS.md) |
| Every decision with its reason, including reversals and dropped approaches | [docs/DECISIONS.md](docs/DECISIONS.md) |
| Verified facts about each job source and outside service (limits, terms, formats) | [docs/SOURCES.md](docs/SOURCES.md) |
| The owner's original concept: frozen, never edited | [docs/HANDOVER.md](docs/HANDOVER.md) |
| Everyday-user documentation | [README.md](README.md) and [docs/guides/](docs/guides/) |
| Setup for people, and the prompts for AI assistants | [CONTRIBUTING.md](CONTRIBUTING.md) |
| What changed, when and why in detail | git history, through clear commit messages |

**Nothing that matters may live only in a chat**, in an AI tool's private memory, or in a file
outside the repository: sessions end without warning, context gets compacted, and the next person
may use a different AI.

When records disagree: the code and tests show what *is*; DECISIONS.md (the newest row on a topic)
says what was *decided*; items marked **Decided** in HANDOVER.md stand unless DECISIONS.md records
a later decision. Correct the wrong record in the same commit as the change that exposed it.

## Sessions: start, work, stop

Treat interruptions as normal: usage limits, context compaction, crashes, lost connections or a
closed terminal can end a session at any moment. Work so that the repository alone always tells
the next session exactly where things stand.

### Starting, or resuming after any interruption

1. Bring this copy up to date: `git status` first (changes that aren't committed mean an
   interrupted task: read them before anything else), then `git pull` and `uv sync`. Work done in
   cloud sessions or by friends arrives only through GitHub, so a copy on the owner's Mac can be
   far behind after a cloud period.
2. Read **"Right now"** at the top of `docs/PROGRESS.md`, and compare it with reality:
   `git log --oneline -5`, `gh run list --limit 3` (did the last push pass on GitHub?) and
   `uv run pytest`.
3. If **In progress** names a task, check each of its steps against the code and tests, then finish
   it or undo it cleanly. If `git status` shows changes that "Right now" doesn't explain, read
   them (`git diff`) before touching anything.
4. Go through **Verify before relying on**, and read the DECISIONS.md sections for the area you'll
   work on (rows marked *Superseded* no longer apply). Read SOURCES.md before touching a source.
5. Clean up what a stopped session may have left: a preview server on port 8799, a scratch copy of
   someone's data folder, temporary files.

### While working

- **Before any task with several steps**, write it under **In progress** in `docs/PROGRESS.md`:
  the goal, the steps, and how to check it's done. Tick steps off as they're finished. It is the
  only record of half-finished work that survives an interruption.
- **Work in small, finished steps**: each one tested, committed and pushed, with its records
  updated in the same commit (a decision → DECISIONS.md, a source fact → SOURCES.md, a changed
  screen or message → the user guides). Then check that GitHub's tests pass.
- **A decision that replaces an older one**: add the new row, and mark the old row
  *Superseded (date): see …* so nobody has to work out which one wins.
- **When a task is done**, empty In progress and update the state, the milestones and Next tasks.
- **Don't keep a diary.** Git history says what was done; PROGRESS.md says only where things stand.

### Ending a session

Do this when the owner asks to wrap up, when the conversation is getting full, or before stopping
for any reason:

1. Stop at a safe point: finish the current step, or leave it described under In progress (what's
   done, what's left, the exact next action).
2. Put everything worth keeping from the session in its home (see the table above): decisions and
   the owner's answers, source facts, lessons, things that still need checking.
3. Update "Right now": the date, state, In progress, Verify before relying on, Waiting on the
   owner, Next tasks.
4. `uv run ruff check . && uv run pytest`, then commit, push and check that GitHub's tests pass.
5. Clean up: stop previews and delete scratch copies of anyone's data.
6. Tell the owner in a few plain lines what was done, what's next, what waits on them, and that
   it's safe to start a new session.

### Working in a cloud session (claude.ai/code)

Since 2026-09-24 the owner mostly works through cloud sessions; Jobcu itself runs on his Mac.

- A cloud session starts on a fresh Ubuntu machine with a clone of the repository. Python, uv,
  pytest, ruff and `gh` are pre-installed, and `gh` works without logging in. At the start,
  `.claude/settings.json` runs `tools/cloud_setup.sh` (the packages, and the safety check before
  every commit). The environment's network access must be **Full**, so job sites, GeoNames and
  documentation can be reached; if a site can't be reached, say so rather than guess.
- **No personal data in the cloud.** The owner's CV, data folder, database and keys stay on his
  Mac. Never ask him to upload them; work with fake data. Full searches with made-up people (a
  fake CV built in code, the AI credential below, the sources that need no key) run fine in the
  cloud and test Jobcu for everyone. What needs his real data (his searches, the score check,
  the coverage test on his answers) happens on his Mac: he runs a 72-hour search every two or
  three days while Jobcu is developed, and a short local session studies it ("Check my latest
  search" in CONTRIBUTING.md) and records the findings in PROGRESS.md. His launcher updates his
  copy from GitHub, so his searches always use the newest merged version.
- **AI tests with a real provider** in the cloud only through an **API credential** the owner
  saved on the cloud environment: the agent proxy adds the key to requests for that host, and
  nobody sees it. Save a placeholder key in a scratch data folder so Jobcu's code runs, and check
  that the first request is answered. Python 3.13 rejects the proxy's certificate for that host
  ("CA cert does not include key usage extension"): at the top of the test script, before
  importing Jobcu, wrap `ssl.create_default_context` so it clears `ssl.VERIFY_X509_STRICT`
  (a cloud-only workaround; never in Jobcu's code). Jobcu's job-site client ignores the
  environment's settings, so a live source check in the cloud passes
  `PoliteClient(transport=httpx.HTTPTransport(verify=ssl.create_default_context(
  cafile=os.environ["SSL_CERT_FILE"])))`. Without such a credential, name the checks that must run
  on his Mac.
- **Branches and merging.** Work on the session's branch and push after every finished step (the
  branch is what survives if the session ends). Open a pull request early; when GitHub's tests
  pass (`gh pr checks`), merge it with a **merge commit** if the owner allowed it in the session,
  otherwise ask him to merge. Then carry on from an updated main. PROGRESS.md is kept current on
  the branch and reaches main with each merge.
- **Budget and the final handover.** The owner's cloud work is paid only by his $100 cloud
  credit (until 2026-11-05); he never wants to pay more, and afterwards he continues in local
  sessions on his Mac. A session can't see the credit left, so: merge every finished step at
  once (a stop at any moment then loses at most the step in hand), work in one session at a
  time, keep the context lean (read what you need, not whole folders), and spend tokens on what
  improves Jobcu. When he says the credit is nearly used, or sends the final-handover prompt
  (CONTRIBUTING.md), stop new work at a safe point and do a complete check-up: `uv run ruff
  check . && uv run pytest`, GitHub's tests on the last merge, every branch merged or its
  unfinished work described under In progress, no pull request left open without a reason. Then
  rewrite "Right now" for a local session on his Mac: the state, what the cloud sessions did,
  what they couldn't check without his data, and the next tasks in order. Merge, and tell him
  it's safe to continue locally. The owner then continues in Claude Code on his Mac (the start
  routine pulls the cloud work first) and restarts Jobcu there to use the new version. Every
  cloud session works with that return in mind: nothing it needs later may live only in the
  cloud session or its chat.

## Who you are working with

The owner (Utku) and his invited friends. **Assume they have no programming experience**, unless
they say otherwise. The owner uses a MacBook and prefers choosing from a few clear options over
answering open questions.

- Explain what you do and why in plain words. Explain any technical term the first time.
- For anything they must do themselves, give exact steps **one at a time** and confirm each one
  worked before the next. Remember that some use a Mac and some use Windows.
- Do the technical work yourself whenever you can.
- **Never ask anyone to paste an API key or password into the chat.** Keys are entered only in
  Jobcu's own settings screen, or, for cloud development sessions, as an API credential on the
  cloud environment, which no session can read ("Working in a cloud session"). If a person allows it, an assistant running on their own computer
  may use the keys saved in Jobcu's data folder **through Jobcu's code** for real tests, without
  ever printing, logging or copying them. Keep usage within the budget below, and job-site
  requests modest (their keys have daily limits).
- **The sessions own Jobcu's decisions** (the owner, 2026-09-24: "you are the owner of this
  project so you should decide on everything and also do the merge add remove stuff"): product
  and technical choices, including changes to items marked **Decided** in HANDOVER.md, are the
  session's own, recorded in DECISIONS.md with their reasons; merging, adding and removing too.
  The hard rules below still hold, and some things only the owner can do: anything that costs
  money or touches his accounts, messages sent in his name (such as asking a platform for
  permission), his own searches, ratings and coverage list. Friends' changes go through pull
  requests the session reviews.

## Hard rules (never break these)

1. **No logins on job sites**, ever: no accounts, cookies or credentials. Never try to get past
   CAPTCHAs, logins or bot protection. If a site blocks Jobcu, back off and mark the source
   unavailable for that search. Respect every site's robots.txt and terms, and every service's
   terms (for example what may be stored, and for how long).
2. **Device-local only:** no website, hosting, server, cloud storage, user accounts, analytics or
   telemetry. Jobcu connects only to job sources, to the AI provider the user chose and, only if
   the user saved a key for it, to Google Maps for travel times (the owner's decision).
3. **macOS and Windows are both fully supported.** Every feature, file path and launcher must work
   on both, and CI tests both.
4. **Stay neutral about AI providers.** Never recommend, prefer or default to one, in code, UI or
   docs. Never hard-code model names: users enter or pick them in settings.
5. **Never commit keys, CVs or personal data.** Tests use fake data only.
6. **The repository is private and its history is permanent:** never make it public, force-push,
   rewrite or squash shared history, or delete commits. Pull requests are merged with a merge
   commit, never squashed or rebased. Commit dates are the record of the owner's work.
7. English UI only. Supported countries only: the 30 in `countries.py`.

## When goals conflict, decide in this order

1. Never break the hard rules.
2. Don't miss relevant fresh jobs. Coverage and freshness are Jobcu's main purpose.
3. Accurate filtering and scoring.
4. Simplicity for non-technical users.
5. Reasonable cost: free is best, cheaper is better. The owner accepts up to €25 a month in
   total for AI and any other service (more freely while Jobcu is being developed); his friends
   and other users want to stay free, and under €10 a month at most, so Jobcu must work well
   on free allowances and cheap models. Never save money by lowering 2 or 3. Optimise requests
   cleverly: never fewer fresh jobs or worse scores.
6. Speed matters least. A search may take minutes, but not hours.

## How a search works

`search.py` runs these steps in a background thread; the screen asks for progress once a second:

documents → profile (`profile.py`) → location plan (`location.py`) → search words (`keywords.py`)
→ sources in parallel (`pipeline.collect`, `sources/*`) → duplicates (`dedupe.py`) → fixed rules
(`filters.py`) → the location conditions that need no measuring → quick relevance check
(`relevance.py`; it also reads the town from the ad text when the job sites give only a country,
and the conditions are then applied to those jobs) → travel limits (`travel.py`) → full ads
(`load_details`) → scoring (`scoring.py`: the AI reads the evidence, code applies the limits for
blockers) → the best jobs looked up online (`jobplace.py`: the town of those without one, and the
full ad's languages and years for those scored from a summary), then the conditions and limits
again for them → cards and job memory (`pipeline.build_card`, `jobstore.py`).

Everything after the rules runs in `search._decide`. **Edit** (next to "Understood as") runs it
again on the same jobs with corrected conditions, reusing every earlier answer (`pool.py`).

## The location box

People write a sentence, not a filter: *"Dublin or Cork"*, *"at most 50 minutes by public
transport to a city with at least 0.3% of the country's people"*, *"no cities where far-right
parties are strong"*, *"a top-10 country for work-life balance"*, *"a Turkish supermarket nearby"*.

- **Every search is different.** Nothing about anyone's wording is hard-coded or carried over:
  the person's AI reads the text fresh each time and splits it into conditions.
- **The AI analyses any fact itself.** Sizes are computed from the shipped figures; everything
  else is looked up on the web through the person's own AI provider, answered as towns that fit,
  towns to avoid, a size rule or countries (which also narrow the countries searched), with
  sources. When nothing lists every place, the AI reasons to a rule and labels it an estimate.
- **Limits to reference places are one condition** ("near"): a time or distance, measured to
  places defined by size, name or any looked-up fact, from where the job ad says the job is.
- **Show the working.** "Understood as" lists every condition, how it was checked and its
  sources; estimates are labelled; the person can correct everything with Edit.
- **Shipped data is only a ruler.** The town list (coordinates, population, local names) measures
  what the AI decided to measure; it never decides what someone meant.

## Project layout

```
Start Jobcu.command / .bat   double-click launchers (macOS / Windows)
src/jobcu/
  launcher.py                starts the local server and opens the browser (__main__.py: python -m jobcu)
  app.py                     FastAPI app: screen, internal API, local-only safety checks
  paths.py                   the per-user data folder (never inside the code folder)
  keystore.py                API keys, saved in the data folder, readable only by the user
  settings.py                all other settings (settings.json in the data folder)
  settings_api.py            internal API behind the Settings screen
  documents.py               CV and cover letter: saving uploads and reading their text
  documents_api.py           internal API for documents and the profile preview
  profile.py                 the AI prompt that reads documents into a profile
  countries.py               supported countries, their job-ad languages and populations
  location.py                understands "Where do you want to work?": conditions, web research,
                             size rules, country answers, corrections from Edit
  travel.py                  travel limits to reference places: Google Maps with the user's key,
                             otherwise AI estimates (remembered 30 days)
  places.py                  the shipped town list: finding towns, populations, distances
  placenames.py              which country a free-text job location is in
  quality.py                 the score check: ads kept from real searches and the owner's answers
  quality_api.py             internal API behind the Score check screen
  keywords.py                the hidden multilingual search words
  search.py                  runs a search (or a correction) step by step, with progress
  pipeline.py                collecting from sources, full ads, result cards
  dedupe.py                  duplicates, main link, "possible duplicate"
  filters.py                 the fixed rules (dates, types, remote, country, dismissed) and
                             conditions
  relevance.py               the quick AI relevance check
  jobplace.py                the best jobs looked up online by the person's AI: their town, and
                             their full ad's languages and years when only a summary was read
  scoring.py                 the scoring rubric and prompt
  freshness.py               posting dates and "Posted within"
  jobstore.py                jobs remembered between searches, job states, saved results
  pool.py                    the latest search's jobs, so Edit can apply corrected conditions
  text.py                    job ad HTML to plain text
  jobposting.py              reads schema.org JobPosting data from job pages
  search_api.py              internal API for starting and following a search
  build.py                   code fingerprint, so a new Jobcu replaces an older running one
  db.py                      SQLite database with numbered migrations
  logs.py                    log file in the data folder, with keys hidden
  ai/                        the AI layer: client.py is the ONLY way to call an AI;
                             one adapter per provider; providers.py lists them
  sources/                   job sources: base.py (common interface), http.py (polite
                             requests), budget.py (usage limits), matching.py (titles and
                             places matched on Jobcu's side), careers.py (company career systems
                             and the employer directory), one module per source
  data/                      shipped reference data: employers.json, places.csv.gz,
                             regions.csv.gz
  web/                       the screen: plain HTML, CSS, JS (no build step)
tests/                       pytest; conftest.py gives every test a throwaway data folder
tools/check_no_secrets.py    safety check against keys and personal data (Git hook and CI)
tools/cloud_setup.sh         prepares a cloud session (run by .claude/settings.json)
tools/check_employers.py     checks the employer directory and adds new candidates
tools/update_places.py       rebuilds the shipped town and region lists from GeoNames
tools/coverage_test.py       how many jobs a person found by hand did Jobcu find, and why not
tools/universality_check.py  made-up people from other fields through profile, search words,
                             quick check and scoring, with the search words checked against ESCO
tools/made_up_search.py      one complete search for a made-up person (by default a graduate
                             power-electronics engineer), in its own data folder
tools/score_check.py         Jobcu's scores against the owner's own answers, and prompt variants
.githooks/pre-commit         runs the safety check before every commit
.claude/settings.json        Claude Code's shared settings: the cloud session setup
.github/workflows/tests.yml  CI: safety check, then tests on macOS and Windows
docs/                        PROGRESS, DECISIONS, SOURCES, HANDOVER, guides/
```

`tests/test_docs.py` checks that this map lists every module and tool, that links between
documents work, and that PROGRESS.md keeps its recovery sections.

## Commands

```bash
uv sync                                  # install everything (uv also installs Python 3.13)
git config core.hooksPath .githooks      # turn on the safety check (once per copy)
uv run pytest                            # run the tests
uv run ruff check .                      # check code style
uv run jobcu                             # start Jobcu
```

Environment variables: `JOBCU_DATA_DIR` uses another data folder, `JOBCU_NO_BROWSER=1` doesn't open
the browser, and `JOBCU_SELFTEST=1` starts Jobcu, checks that it answers, then stops.

**Real tests with someone's own AI and keys** (only with their permission, see above): copy their
data folder to a scratch folder, point `JOBCU_DATA_DIR` at the copy, and delete the copy when
done. Run a preview on port 8799 (a person's own Jobcu uses 8765):
`uv run uvicorn --factory jobcu.app:create_app --port 8799`. To check only how the AI reads a
location sentence (a few AI requests, no job sites), call `location.interpret_location` from a
short script with that `JOBCU_DATA_DIR`.

## Conventions

- **Python 3.13 with uv.** Add dependencies with `uv add` (or `uv add --dev`) and commit `uv.lock`.
- **Style:** Ruff, line length 100. Comments explain *why*, in plain words.
- **Tests:** every change comes with tests, and they must pass on macOS and Windows. Use `pathlib`,
  never OS-specific path strings, and always pass `encoding="utf-8"` when reading or writing text.
- **Screen:** plain HTML/CSS/JS in `src/jobcu/web/`. No build tools, CDNs, web fonts or outside
  scripts. The Content-Security-Policy and a test enforce this.
- **Local server:** listens on 127.0.0.1 only. Requests that change data must send the header
  `X-Jobcu: 1` from Jobcu's own page. Other requests are refused.
- **User data** (documents, jobs, job states, settings, keys) lives only under `paths.data_dir()`.
- **Database changes** are new numbered migrations in `db.py`; never change one that has been
  pushed, because people's databases have already applied it.
- **Keys** go through `keystore.KeyStore`. Never log them, and show them only masked.
- **AI calls** all go through one provider layer, never directly to a provider SDK from elsewhere,
  so switching provider is only a settings change.
- **Job sources:** one isolated adapter per source behind a common interface. A failing source
  must never break a search. Be polite: limit request rates, back off on errors and respect
  `Retry-After`.
- **Text users see:** friendly, plain English without jargon.
- **Two audiences for documents.** Everyday users: `README.md` and `docs/guides/`, short and simple,
  with no technical words and no filler, just enough to use Jobcu fully. Developers: this file and
  `docs/`, technical and detailed. When a screen, message or step changes, update the user guides
  in the same commit.
- **Coverage:** reach as many jobs as possible, for every kind of work, in **all 30** supported
  countries, through every legally safe route, not only APIs (see DECISIONS.md). The order of
  work (the owner, 2026-09-24): 1. Germany; 2. the UK and Ireland; 3. Switzerland; 4. Belgium;
  5. the Netherlands; 6. Italy; 7. Scandinavia (Denmark, Norway, Sweden); 8. Poland; the rest
  later. That's an order, not a limit; for now only Germany, the UK and Ireland get new work
  (the owner, 2026-09-24, see "Where the work goes first").

## Lessons learned (avoid repeating these mistakes)

- **Check the test result before committing.** Piping pytest output through `tail` or `grep`
  hides failures. Use `uv run pytest && git commit …` or `set -o pipefail`.
- **Wait for GitHub's tests after every push** (`gh run list`, `gh run view <id> --log-failed`).
  Windows exposes timing and path bugs that macOS doesn't.
- **Never contact real sites in tests.** Use `httpx.MockTransport` with
  `PoliteClient(min_intervals={}, sleep=…, transport=…)`, and the scripted AI adapters in the tests.
- **An owner's decision only counts once the code applies it.** "Dominant election result" was
  decided on 2026-09-17 but missing from the AI's instructions until 2026-09-22. When recording a
  decision that changes behaviour, change the code or prompt in the same commit.
- **Check a service's terms before storing its answers.** Google's Routes API terms allow keeping
  coordinates for 30 days, not travel times.
- **Try new AI instructions with a real provider**, on a copy of someone's data (see Commands):
  scripted tests can't show whether a model reads a sentence the way people mean it.
- **A model answers from memory unless told to search.** "Find where this job ad is" came back
  with company head offices and no web search at all until the instructions said to search for
  every job and called an answer from memory a guess. Check `usage.web_searches` to see which it
  did.
- **Measure a search word before spending a budget on it.** Adzuna's `count` (one request) showed
  that two general words made one query match 6,459 ads instead of 337, which had been eating the
  whole request budget on ads nobody wants.
- **A daily limit belongs to the service's day, not the user's.** Google's Routes quota resets at
  midnight Pacific, so an evening search and one after midnight in Europe share it.
- **What only a tooltip shows doesn't exist.** The owner asked how a one-point score difference
  arises; the breakdown was there, but only on hover.
- **Import loops can hide behind a lucky import order.** `tests/test_imports.py` loads key modules
  on their own; import heavy modules inside a function when two modules need each other.
- **Try AI instructions with someone else's words too.** One made-up person's sentence
  (Netherlands, trains, a technical university, no rain) found two general faults the owner's
  own sentence never showed: a cut-off answer and "fit" swapped with "avoid".
- **Thinking counts as output with every provider.** Raising the reasoning effort cut off a
  2,000-token answer; `ai/client.py` now adds room for thinking to every request.
- **A site that blocks Jobcu stays blocked.** Find the data another way (the same job elsewhere,
  the person's AI reading it online) instead of trying again each search.
- **Python's robots.txt reader gets the standard wrong.** `urllib.robotparser` takes the first
  matching rule, so "Disallow: /" followed by "Allow: /careers" refused allowed pages. Use
  `sources.http.RobotsRules` (RFC 9309: the longest rule wins).
- **Measure coverage with a whole search, not a source on its own.** Each new source looked fine
  alone; only `tools/made_up_search.py` showed that the directory's career sites gave nothing
  for a hardware engineer around Munich or in Dublin.
- The secrets check can flag public identifiers. Only if a value is clearly not a secret, add
  `# jobcu-guard: allow` with a comment explaining why.

## Contributing

Friends work on a branch in their own copy and open a pull request; the owner approves merges.
Every commit: `uv run ruff check .` and `uv run pytest` pass, the safety hook is on, and the
records above are updated in the same commit.
