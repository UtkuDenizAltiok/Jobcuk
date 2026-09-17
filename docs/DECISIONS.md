# Jobcu decision log

Every decision made while building Jobcu, with a short reason, newest phase at the bottom.
Decisions marked **Decided** in the [original concept](HANDOVER.md) come from the owner and
aren't repeated here unless something about them was clarified.

---

## 2026-09-17: Phase 0, Foundations

### Confirmed with the owner

| Decision | Reason |
|---|---|
| The copyright holder's name is spelled **Utku Deniz Altiok** | Confirmed by the owner before the first commit, as the concept document requires. |
| The helper tool **uv** is installed on the owner's Mac through Homebrew | The owner agreed. Homebrew was already on the Mac, so this was the simplest route. |
| The code lives in a **private GitHub repository called `jobcu`** on the owner's account | The owner agreed. |

### Technology

| Decision | Reason |
|---|---|
| **Python 3.13** for the app's engine | A proven version that all the building blocks we need support on macOS and Windows. |
| **uv** installs Python and the building blocks, and starts the app | One small tool does everything on both macOS and Windows, so nobody has to install Python by hand. Exact versions are locked in `uv.lock`, so every computer gets the same setup. |
| **FastAPI** with **Uvicorn** for the local web server | Widely used and well maintained. It suits Jobcu's screen talking to its engine, can show search progress live, and checks the AI's structured answers. |
| **Plain HTML, CSS and JavaScript** for the screen, with no build tools | No extra tools to install or keep updated, and the files can be read and fixed directly. |
| **System fonts only; the screen never loads files from the internet** | The concept allows connections only to job sources and the AI provider. A security rule in the page enforces this, and a test checks it. |
| **SQLite** will store job states (Saved, Applied, Not interested, already seen) | Built into Python, a single file in the data folder, and needs no setup. The database arrives in Phase 1, when there is something to store. |

### Where data lives

| Decision | Reason |
|---|---|
| Data folder on macOS: `~/Library/Application Support/Jobcu` | The standard place for app data on a Mac. It's outside the code folder, so updates never touch it. |
| Data folder on Windows: `C:\Users\<name>\AppData\Local\Jobcu` | The standard place for app data on Windows. "Local" (not "Roaming") keeps it on that one computer. |
| The data folder holds a short `README.txt` explaining what it is | So anyone who finds the folder knows not to share or delete it by accident. |
| **API keys are stored in `keys.json` inside the data folder**, readable only by the user's own account, instead of in the Mac Keychain or Windows Credential Manager | The concept allows either. The Keychain can show confusing "python wants to access your keychain" pop-ups after updates, and it behaves differently on Windows. A private file in the data folder works the same everywhere. Keys are never logged and are only shown masked (`••••3f9a`). |

### Safety

| Decision | Reason |
|---|---|
| Jobcu's server only accepts connections **from the same computer** (127.0.0.1) | Nobody else on the same Wi-Fi can open it. |
| The server **refuses requests addressed to other website names**, and anything that changes data must carry a Jobcu-only header from Jobcu's own page | Stops other websites open in the same browser from using Jobcu, or your AI key, behind your back. |
| A **safety check** (`tools/check_no_secrets.py`) blocks API keys, CV-type documents (PDF, Word, etc.), databases and key files | Required by the concept. It runs before every commit on the owner's Mac (a Git "hook", an automatic step Git runs first) and again on GitHub after every upload. Fake test documents are allowed only in `tests/fixtures/fake_documents/`, named `fake_*`. |
| `.gitignore` also keeps these files out, from the first commit on | A second layer of protection, so the files are never even offered for upload. |

### Starting the app

| Decision | Reason |
|---|---|
| Double-click **`Start Jobcu.command`** (Mac) or **`Start Jobcu.bat`** (Windows) | The simplest one-action start on each system. |
| A small text window stays open while Jobcu runs; **closing it stops Jobcu** | Easy to understand, and messages stay readable if something goes wrong. A more polished start can come in Phase 4. |
| Jobcu always tries the same address, `http://127.0.0.1:8765`, and uses another free one only if that's taken | The address stays the same, so a bookmark keeps working. |
| Double-clicking Start while Jobcu is already running just opens it in the browser | Prevents two copies running at once. |

### Testing and GitHub

| Decision | Reason |
|---|---|
| **Automatic tests on GitHub on both macOS and Windows** after every upload, including starting Jobcu with the real launcher files | The concept requires Windows support from the start. |
| Tests always use a throwaway data folder | Tests can never touch anyone's real data or keys. |
| The GitHub tests use the account's **free monthly allowance of test minutes** | No cost. Without a payment method on file, GitHub simply pauses the tests when the allowance runs out. |
| The repository starts on the owner's personal GitHub account. **Before friends are invited (Phase 4), it moves to a free GitHub "organization"** (a shared space on GitHub) | On a personal account, anyone given access can also change the code. An organization lets the owner choose per friend: download-only (the original plan) or allowed to propose changes that the owner approves. The owner mentioned that friends may contribute later, so this choice is made with him in Phase 4. Moving keeps all history and dates. |
| The concept document is kept unchanged at `docs/HANDOVER.md` from the first commit | The concept requires this as a dated record of the owner's work. |

### The owner's own AI provider

| Decision | Reason |
|---|---|
| For **his own copy** of Jobcu, the owner chose **Google (Gemini)** after a neutral comparison | His choice. It only affects his settings: Jobcu itself still recommends no provider and has no default, and every user picks their own. |
| He starts on Google's **free allowance, with no billing set up yet** | Nothing is paid for before real usage is measured in Phase 1. If paid use turns out to be needed, the owner is asked first and shown how to set a monthly spending cap. |
| The owner's Adzuna, Reed and Gemini keys are kept in Apple's Passwords app until Jobcu's settings screen exists | Keys are never pasted into chat or saved in the code folder. |

### Backups and sharing

| Decision | Reason |
|---|---|
| **No separate backup copies. GitHub is the backup.** This replaces the backup suggestion in HANDOVER section 14.1. A backup tool was built, tested, then removed on the owner's request. | The owner's decision: GitHub already keeps the full dated history. |
| **Everything that isn't private goes to GitHub:** code, the concept document, the decision log, progress, setup and contributor instructions, and the guides | The owner wants the repository to be complete and up to date, so friends can understand the project and possibly contribute later. Private things (keys, CVs, personal data, the owner's own settings) never go there, and the safety check enforces this. |
| **Friends may improve Jobcu, possibly with their own AI coding assistants.** The repository stays private: invited friends only, never public. | The owner's decision (2026-09-17). It updates HANDOVER 14.1, which planned download-only access. Friends still can't change the main code directly: they propose changes as pull requests, and the owner approves them. |
| **`AGENTS.md` holds the instructions for all AI coding assistants.** `CLAUDE.md` just imports it, `.gemini/settings.json` points Gemini CLI to it, and `.aider.conf.yml` points Aider to it. | AGENTS.md is the shared standard read by most AI coding tools (Codex, Cursor, Copilot, Gemini CLI, Windsurf, Junie, Aider and more). One file means no copies drifting apart, whichever tool a friend uses. |
| **`CONTRIBUTING.md` explains setup and sending changes in plain words**, for Mac and Windows | Friends may not be programmers. |
| Friends contribute from **their own private copy (a fork) through pull requests** | Branch protection isn't available for private repositories on free GitHub plans. Forks with pull requests keep the owner's main code and its history safe at no cost. |
| `CONTRIBUTING.md` says contributions become part of Jobcu under its LICENSE | Keeps Jobcu clearly the owner's work, in friendly wording with nothing to sign. |
| GitHub forms for pull requests, problem reports and ideas | Helps non-programmers describe changes and problems clearly, and reminds everyone not to share keys or personal data. |
| **`.editorconfig`** sets shared text settings (UTF-8, line endings, indentation) | Understood by most editors and AI tools, so files stay consistent on Mac and Windows. |
| The keys guide (`docs/guides/getting-your-keys.md`) is written now, from the steps the owner actually followed, with neutral instructions for several AI providers | Keeps the verified steps instead of losing them in a chat. Screenshots follow in Phase 4. |
| A test checks that links between the project's documents still work | Friends and AI tools will edit the docs, and broken links would confuse readers. |

---

## 2026-09-17: Phase 1, Usable first version

### Confirmed with the owner

| Decision | Reason |
|---|---|
| **Job sources: clearly permitted sources first.** Official job APIs, government job agencies, company career systems and AI web search are built. Reading LinkedIn, Indeed, StepStone, Glassdoor etc. pages directly is **on hold** until the coverage test (Phase 3) shows how many jobs would really be missed. | The owner wants to avoid legal risk. This updates HANDOVER 9.4, which had accepted that grey area. |
| **Score check: "quick review".** Claude collects about 40 real job ads and pre-fills a rating for each; the owner only corrects the ones he disagrees with. | The AI still scores every job automatically in every search. This one-time answer key checks that the scores match the owner's own judgement, with less work for him than rating everything. |
| **Cover letters may be written for one specific application.** When reading a cover letter, Jobcu ignores everything specific to that one application (the company, that job title, that company's country or city, plans to move there) and keeps only what's generally true about the person and what they want. **Where to work comes only from the location box.** | The owner's instruction. HANDOVER assumes a generic cover letter, but real ones are often tailored. |

### Technology

| Decision | Reason |
|---|---|
| Each native AI provider is reached through **its official Python library** (`google-genai`, `openai`, `anthropic`), wrapped in Jobcu's own AI layer. "Other (OpenAI-compatible)" providers use the `openai` library with the provider's address. | The providers maintain these libraries and keep them current, which matters because AI APIs change often. Jobcu's layer makes every provider behave the same for the rest of the app. |
| The libraries' own automatic retries are switched off; **Jobcu's AI layer retries** instead | Waiting and the plain messages ("AI limit reached, continuing more slowly") then work the same for every provider, and no progress is lost. |
| OpenAI requests use `store=False` | The concept keeps user data private; this asks OpenAI not to keep the conversation for later use. |
| **No copyleft libraries** (GPL, AGPL and similar) | Jobcu is "all rights reserved", and those licences could require publishing its code. |

### AI settings and keys

| Decision | Reason |
|---|---|
| Providers are shown **alphabetically**, with "Other (OpenAI-compatible)" last, and **none is pre-selected** | Neutrality: Jobcu never suggests a provider. |
| Each provider's key is saved separately (`ai_anthropic`, `ai_gemini`, …) | Switching provider doesn't delete the other keys, so switching back is easy. |
| Model names come from the provider's own model list (the "Load model list" button) or are typed in; **none is built into Jobcu** | Providers rename and retire models often (HANDOVER §13). |
| Reasoning effort starts at "low" for scoring and "medium" for reading documents and the location; models that don't support a setting are retried without it automatically | HANDOVER §13 asks for the lowest setting that keeps quality. These starting values get checked against the quality test set. |
| The setup check asks the model for a tiny answer in Jobcu's JSON format, and reports rate limits instead of waiting | The check has to be quick and prove that structured answers work, not just that the key is valid. |
| Saved keys are shown only as their last four characters | Enough to recognise a key without revealing it. |
| The log file hides anything that looks like a key, and the Adzuna check never logs its request address (which contains the key) | A safety net against keys ending up in log files. |

### CV, cover letter and profile

| Decision | Reason |
|---|---|
| Documents are read with **pypdf** (PDF) and **python-docx** (Word), both permissive licences | Well maintained and install on Mac and Windows without extra tools. |
| **PDFs are read two ways** (plain and layout-aware) and the cleaner result is kept | Different PDF programs store text very differently. The owner's own CV reads best one way and his cover letter the other. |
| A file is **read when it's uploaded**, so problems (scanned image, password, damaged file) show up right away with advice | Better than finding out in the middle of a search. |
| **Text is never cut.** Documents longer than 60,000 characters are refused with a message | Silently cutting a document could leave out important details. No real CV or cover letter is that long. |
| Uploaded documents are stored in the data folder, readable only by the user | They're personal data. |
| The AI reads the documents with the **"careful" model and reasoning setting** (the optional second model) | HANDOVER §13 names reading the CV and cover letter as a reasoning-heavy step. |
| The profile lists **what was left out because it was about one specific application** | People can see that company names, job titles and countries from a tailored cover letter weren't used. |
| The profile keeps languages **as written**, plus a CEFR level marked "estimated" when it comes from words like "fluent" | Honest about what's stated and what's guessed. It helps scoring without claiming certainty. |
| Document text is marked as data in the prompt, and the AI is told to ignore instructions inside documents | Protects against text in a document that tries to steer the AI. |
| "What Jobcu understood" can be opened before any search, and **nothing is saved** | People can check the AI understood them before searching. HANDOVER §4 says the profile isn't kept. |

### Real tests with the owner's keys

| Decision | Reason |
|---|---|
| **The owner allowed Claude to use his keys for development** (2026-09-17). Claude uses the keys already saved in Jobcu on his Mac, only through Jobcu's own code, and never prints, logs, copies or commits them. | Real tests with the real AI and real job sources give much better development than made-up data. Keys never have to appear in the chat: it's stored outside the owner's computer and adds no benefit, because Claude already works on that computer. |
| Development tests use **free usage only**. Claude asks before anything that could cost money, and keeps Adzuna and Reed requests modest. | The owner's Gemini account has no billing set up, and the job-site keys have daily limits. |
| **Experience is split into full-time years and internship / working-student / part-time years** | The first real test counted the owner's part-time student jobs as "3.1 years of experience". Job ads asking for "3+ years" usually mean full-time work, so that would have overstated seniority fit. |

### Location, search words and running a search

| Decision | Reason |
|---|---|
| **A newer Jobcu automatically replaces an older copy that's still running** (the code has a fingerprint; the new copy asks the old one to stop) | The owner double-clicked Start Jobcu after an update and still saw the old screens, because the old copy was running. |
| Phase 1 location understanding handles **named countries, regions and places**. Any other condition is shown as "Not checked yet" until the smart filter in Phase 2. An empty box means all 31 countries, with a note that this takes longer. | Matches the phased plan (HANDOVER §16). Nothing is silently ignored. |
| The AI doesn't guess countries for descriptions like "by the seaside" | Guesses about places belong in Phase 2, where they'll be checked against real data or clearly labelled "AI estimate". |
| **Search words:** up to 16 job titles and 8 field or skill words per language, in English plus the job-ad languages of the countries searched (a small table in `countries.py`). At most 5 languages per AI request. | Covers the common title variants employers use (HANDOVER §5) while keeping requests reliable and affordable. |
| Search progress is shown by the screen **asking Jobcu once a second** | Simpler and sturdier than a live connection, and plenty fast for a search that takes minutes. |
| **One search at a time** | Keeps usage predictable and avoids two searches competing for the same free AI allowance. |
| The search form (location text and filters) is **remembered for the next visit** | Convenience only. Every search still reads the documents and the location text again from scratch. |
| After a search, "What Jobcu understood" shows **exactly what that search used**. Before any search, it reads the documents on the spot. | The user sees what the search really worked with. |

### Owner's choices for the smart location filter (Phase 2 design, decided 2026-09-17)

Based on the owner's own test sentence: *"Germany or Ireland or UK, no AfD or other fascist supporter
cities (dominant election result). Also the job location should be at most 50 minutes to a city that
has at least 0.3% of its country's total population."*

| Decision | Reason |
|---|---|
| **The AI settles unclear wording itself** instead of asking the user, and shows exactly how it read each condition under "Understood as", where the user can edit it | The owner's principle: interpreting fuzzy wording is why Jobcu uses an AI. It also matches HANDOVER §6 (no confirmation step before searching). |
| **Political conditions:** when the user describes parties by a label (e.g. "far-right" or "fascist supporter") instead of naming them, the AI researches, with live web search, which parties reliable current sources put in that group for each country. It lists the parties it used, with source links, in "Understood as". | The owner asked the AI to research and decide. Showing the parties and sources keeps the choice transparent and correctable. Jobcu itself takes no political position; it applies the user's own condition. |
| **"Dominant election result"** is read as **above the party's national average** in the latest national parliamentary election, unless the user's wording says otherwise. Results come from official sources for each place, so failing places are hidden (verified). | The owner's reading, e.g. Dresden should be excluded. |
| **Travel time** uses the travel mode the user writes. **If none is given, it means public transport.** | The owner's choice. Exact public-transport times need a route-planning source; Phase 2 will look for a free, permitted one and otherwise show a clearly labelled estimate. |
| **Google Maps is the preferred source for travel times**, used **only within Google's free monthly allowance**. The owner doesn't want to pay for it. It stays an **optional key**: without it, Jobcu shows a clearly labelled estimate. | The owner's choice (2026-09-17). Google has the most complete public-transport timetables. Keeping it optional keeps setup simple for friends. |
| Travel time is **one simple number per place**: from the job's town to the **centre** of the nearest big-enough city, by the mode the user writes (default public transport), for a normal weekday trip during working hours. Jobcu asks Google **once per place, not per job**, never for places already inside a big-enough city, never for places obviously too far away, and remembers answers for as long as Google's terms allow. | Keeps usage far below the free allowance: estimated at a few hundred to about 1,500 requests a month, even with 5 searches a day. |
| **Two safety stops against charges:** Jobcu counts its own Google requests and stops well below the free allowance each month, and the owner sets a daily limit in Google's own settings so Google itself refuses anything beyond it. Google needs a payment card on file even for free use; the owner approves before setting that up. Exact numbers and terms are confirmed in Phase 2. | The owner must never be charged for Google Maps. |
| City size given as a share of the country's population is computed per country from official population figures (0.3% ≈ 250,000 in Germany, ≈ 200,000 in the UK, ≈ 16,000 in Ireland) | Follows the user's rule exactly. The very different results per country are shown in "Understood as". |

### Job sources, duplicates, filters and scoring (Phase 1, part 4)

| Decision | Reason |
|---|---|
| **Adzuna** is queried economically: single-word search words are combined into one "any of these words" request, multi-word phrases need a request each (field words first), results come newest first and paging stops at the first job older than the window. Jobcu stops at **40 requests per search, 240 a day and 2,400 a month**, and each country or place gets a fair share. | Adzuna's free key allows 250 requests a day and 2,500 a month. Real tests showed boolean queries like `"a" OR "b"` return nothing. |
| **Reed:** one request per English search word, reading all pages (Reed can't sort by date or combine words); jobs proven older than the window are skipped. | Tested: Reed ignores OR and returns results in no date order. |
| **Bundesagentur für Arbeit:** one request per German or English search word, using the "published since" day filter; the **first publication date** is used, and each job's real country is read from its address. | The first publication date catches reposted old jobs. A real test showed the agency also lists jobs in Austria. |
| **Short versions first, full ads later:** sources return short versions; full ads are fetched only for jobs that survive duplicates, the rules filter and the quick relevance check. | In a real test, fetching every full ad used 250 Reed requests for one week of UK jobs; most were irrelevant. |
| **Adzuna's job pages are read for the full ad** (the owner's decision, 2026-09-17): only for jobs that passed the quick relevance check, reading the page a person sees when clicking the job, with a 3-second pause between pages. A refused page is skipped and never retried; after 3 refusals in a row, or any "too many requests" or robot-check answer, no more Adzuna pages are read in that search. | The API gives only the first ~500 characters of each ad. The owner accepts this grey area for better scores, but never working around a block. A real test showed why it matters: full ads changed scores a lot (a PCB designer job went from 87 to 68 because the full ad asks for good German and a vocational background; another from 96 to 87 because it asks for 5+ years). |
| Adzuna sometimes refuses a **single** ad's page ("Zugriff verweigert") while other pages load normally, so one refusal doesn't stop page reading | Found in a real search: stopping after the first refusal left 4 of 22 jobs with only summaries. |
| Job pages are read through a **general reader for schema.org JobPosting data** (`jobposting.py`), the standard job data most job boards and career sites include for search engines | It gives the full text, posting date, job type and remote status in one format across thousands of sites, and Phase 3 reuses it for company career pages. |
| When a source leads to the **employer's own page**, that page becomes the job's main link, with the source listed under "Also on". Staffing agency ads are excluded. | HANDOVER §10 puts the employer's own page first. An agency's page isn't the employer's. |
| **Company career systems** (Greenhouse, Personio, Workday and others) move to **Phase 3**, together with the employer directory | In 815 real job ads, the employer links from Reed and the job agency pointed to company homepages, staffing agencies and other job boards, never to a career system. Company discovery through links would find almost nothing. |
| Posting dates known **only by day** are hidden only when the whole day lies before the window, and are shown as "posted today" or "posted yesterday" | Such a job can't be proven too old, so it isn't hidden (HANDOVER §7). |
| **Duplicate rules:** copies of the same company and place match when their titles match word by word (typos allowed); titles at a different level ("Senior", "Werkstudent") or with different reference numbers never match; **staffing agency** ads need matching full text to merge, and an agency ad that repeats an employer's own ad is tagged "possible duplicate" | Tested on 588 real ads. Looser fuzzy matching wrongly merged "Lead Electronics Engineer" with "Electronics Engineer", and "Elektronik" with "Elektrotechnik". Agencies (Ferchau, Brunel, Akkodis and others) post near-identical ads for different clients. |
| **Quick relevance check is on** (title, company and the first lines, 40 jobs per AI request). Only clearly unrelated jobs are left out, and their titles are listed in Search details. **Provisional until the quality test set confirms it.** | Without it, a single search can have 300+ jobs to score, which would use up a free AI allowance quickly. HANDOVER §13 requires checking it against the test set, which comes next. |
| **Scoring:** 4 jobs per AI request, each rubric part scored separately and **added up in code**; a job the AI skips is asked about again on its own. Batch size is provisional until the quality test. | The total always matches the parts, and no job silently goes unscored. |
| When the scoring limit is reached, the search **asks** before scoring more. Jobs not scored are **still shown** (without a score). | HANDOVER §13: caps never silently reduce coverage. |
| The last search's results are saved and shown again after Jobcu restarts. Saved and Applied lists include jobs from all searches. "Show hidden" brings back jobs marked Not interested. | HANDOVER §12. |
| In Phase 1, a job's country is labelled **verified** when the source states it. Places and distances rely on each source's own location filter until Phase 2. | Honest labelling until the smart location filter arrives. |

---

## 2026-09-17 (evening): Owner's guidance on usage and money

| Decision | Reason |
|---|---|
| **Expected use: usually 3 searches a day, at most 5.** Limits should fit this real use and must not be so strict that results get worse. | The owner's guidance. Earlier planning assumed 5 a day as the norm. |
| **Adzuna's request budget per search will adapt** to the remaining free monthly and daily allowance, assuming about 3 searches a day, instead of a fixed 40 per search | 2,500 requests a month ÷ about 90 searches ≈ 27 per search on average. A fixed 40 would run out after about 60 searches, while light days leave allowance unused. |
| **Money:** up to **€30 a month in total** for everything (AI first, other services if they clearly help). Free is best and cheaper is better; paying is fine only where it really improves results. Before anything that costs money is set up, the owner is told the expected cost. | The owner's guidance. This replaces the earlier "Google Maps only within its free allowance" rule: Maps may use part of the €30 if it clearly helps, though the owner expects the free allowance to be enough. |
| **Reading full job pages is best effort.** If a site doesn't allow it, Jobcu scores from what it has and carries on; this is never a reason to stop a search. | The owner's guidance: full ads help, but a platform refusing them isn't critical. |

## Working across sessions

| Decision | Reason |
|---|---|
| `docs/PROGRESS.md` starts with a **"Right now"** section (where the project stands, what waits on the owner, the next tasks in order). Every AI session reads it first and updates it after each finished step and before the conversation is cleared. | The owner clears long conversations (`/clear`). Everything needed to continue must live in the project, not in one chat. |
| Hard-won facts about each job source live in **`docs/SOURCES.md`** | Source behaviour (limits, quirks, formats) took real testing to learn and is needed again for Phase 3. |

## 2026-09-17 (evening): First outside tester

| Decision | Reason |
|---|---|
| **The Start Jobcu files install the helper program uv themselves**, after asking (Mac: press Return; Windows: press any key), using uv's official installer from astral.sh into the user's own folder, without changing shell settings. GitHub tests the "helper missing" path on both systems. | The owner is sharing Jobcu with a non-technical friend. Before this, a missing uv meant a dead end. This was planned for Phase 4 but is needed now. |
| **Tester-ready documents now, ahead of Phase 4:** the README first screen for testers, and guides for installing and starting (Mac and Windows, including the Apple "could not verify" and Windows "protected your PC" warnings), the first search, and troubleshooting. Pictures come later. | Someone who has never used GitHub must be able to install and use Jobcu from the repository alone (HANDOVER §2.1). Real tester feedback helps the scoring work. |
| **A tester gets access by being invited to the private repository as a collaborator.** Before more friends are invited, the repository moves to a free organization, as planned. | For one trusted friend this is the simplest path. Collaborators on a personal repository can technically change files, but every change stays visible in the history and can be undone. |
| The GitHub "Download ZIP" keeps the Mac start file runnable (checked: `jobcu-main/Start Jobcu.command` keeps its "can be started" setting) | Otherwise the Mac guide wouldn't work. |

## 2026-09-17 (late evening): Documentation style and country priority

| Decision | Reason |
|---|---|
| **Two audiences, kept apart.** Everyday users get `README.md` and `docs/guides/`: short, simple, no technical words, just enough to use Jobcu fully. Developers get `CONTRIBUTING.md` (developer guide), `AGENTS.md` and the files in `docs/`: technical and detailed. | The owner's instruction: the user side must be clear and sleek, not bloated. Technical detail belongs to developers. |
| **Top-priority countries: Ireland, the UK and Germany.** Other EU and European countries are also important, but these three come first for coverage work and testing. | The owner's instruction. |
| **Ireland wasn't connected yet** because the Phase 1 starter sources (Adzuna, Reed, Bundesagentur) came from the original plan, and Adzuna turned out not to cover Ireland. **Connecting Irish sources is now the next task**, ahead of the rest of Phase 1, and coverage for the UK and Germany is strengthened at the same time. Clearly permitted sources come first (owner's earlier choice). | Coverage is Jobcu's main purpose (HANDOVER §9.0), and Ireland is a top-priority country with no source at all today. |
| **Priority means order, not exclusion.** The goal stays **maximum coverage across every supported European country**: as many platforms, regions and ways of finding jobs as possible, so that whatever places a user prefers, Jobcu covers them well. Ireland, the UK and Germany are simply worked on and tested first. | The owner's clarification (2026-09-17). Matches HANDOVER §9.0: coverage is Jobcu's main purpose. |
| **Don't rely only on sites that offer an API.** Jobcu should reach jobs anywhere on the web, **without legal risk**, through routes like these: official APIs and open data; public employment services of each country and EURES; job feeds that sites publish for sharing (XML/RSS); company career systems' public job lists; the standard job data (schema.org JobPosting) that career sites and boards publish for search engines; an employer directory per country; and the AI provider's live web search to discover job pages anywhere. Always: no logins, respect robots.txt and site terms, never work around blocks, polite pace. | The owner's instruction. Each route is verified first and recorded in `docs/SOURCES.md`. Job boards whose terms forbid automated reading stay on hold until the coverage numbers are in (owner's earlier choice). |

## 2026-09-17 (night): Countries, reusing AI work, optimising requests

| Decision | Reason |
|---|---|
| **Supported countries: every country that lies fully or mostly in Europe** (45 in total), replacing "EU + UK, Switzerland, Norway, Iceland" (HANDOVER §1, §17). Added: Albania, Andorra, Belarus, Bosnia and Herzegovina, Kosovo, Liechtenstein, Moldova, Monaco, Montenegro, North Macedonia, San Marino, Serbia, Ukraine, Vatican City. Not included: countries mostly in Asia (Turkey, Russia, Kazakhstan, Georgia, Armenia, Azerbaijan). Cyprus stays as an EU member. Job-ad languages for each are in `countries.py`. | The owner's decision. The goal is coverage across the European continent. |
| **Reusing AI work: only for understanding the person.** When the CV text and cover letter text are exactly the same as in an earlier search (and the profile prompt and model are unchanged), Jobcu reuses the earlier profile. **Everything about the job search stays fresh every search:** location understanding, search words, finding jobs, the quick relevance check and scores. | The owner's decision. It saves AI allowance without any effect on finding the freshest, best jobs. HANDOVER §4/§12 ("profile not kept") is updated for identical documents only. |
| **Request optimisation must never cost quality: never fewer fresh jobs, never worse scores.** Allowed savings: adaptive per-search budgets for sources with free limits; results that come newest first are paged only until older than the window; full ads are fetched only for jobs still in the running; within a search nothing is fetched twice; the job **ad text** (not scores) may be remembered by job ID for a few days, so the same ad isn't downloaded again; AI requests are batched and use provider-side prompt caching where available. | The owner's instruction: "the best of both worlds". Each saving is measured in Search details. |

| **Supported countries changed to a top 20** (this overrides the 45-country decision above): the 20 European countries with the highest GDP per person (IMF World Economic Outlook 2025, current US dollars), leaving out tiny states under 100,000 people. **Austria, Belgium, Cyprus, Czechia, Denmark, Finland, France, Germany, Iceland, Ireland, Italy, Luxembourg, Malta, Netherlands, Norway, Slovenia, Spain, Sweden, Switzerland, United Kingdom.** Ireland, the UK and Germany are still worked on first; coverage within these 20 should be as complete as possible. Compared with the original list (HANDOVER §1), it no longer includes the EU countries outside the top 20 (e.g. Poland, Portugal, Greece). | The owner's decision: 45 countries would bloat the app and spread the work too thin. Tiny states (Liechtenstein, San Marino, Andorra, Monaco, Vatican City) rank high but have very few jobs. |
| **Supported countries: 30** (this overrides the top-20 decision above): the top 20 plus **Poland, Portugal, Romania, Greece, Hungary, Croatia, Slovakia, Estonia, Latvia and Lithuania**. Still left out: tiny states, and Bulgaria, Serbia and Ukraine among the larger ones. | The owner's decision after reviewing which large and well-known countries the top 20 left out. |
| **Search-word languages follow the location only:** English plus the job-ad languages of the countries searched. When places are named in a country with several languages, only those places' languages are used (Zürich: German; Geneva: French; Brussels: French and Dutch). An empty location still needs every language. | The owner's instruction: no unnecessary translation. Fewer languages means fewer AI tokens and fewer source requests, with no jobs lost, because ads in a place are written in its languages or English. Checked live: "Zürich or Geneva" → English, German, French. |

## 2026-09-17 (night): Coverage work for Ireland, the UK and Germany

| Decision | Reason |
|---|---|
| **JobsIreland.ie is a source** (Ireland's public employment service). Jobcu reads its newest-first job list page by page until jobs are older than "Posted within", matches titles to the search words itself, and reads a job's own page for the full ad only when the job is still in the running. | Ireland had no source at all. There's no API, but robots.txt allows everything and the site's terms say the information is meant for jobseekers searching for work; Jobcu shows it only to the person searching and never re-publishes it. Its own keyword search looks at titles only, so reading the list is the same result with fewer requests. |
| **Sources that can only list jobs are matched on Jobcu's side** (`sources/matching.py`): a job title must contain every word of a job-title search word (in any order, also inside longer words), field words may also match the ad text, and named places must appear in the job's location. | Generous matching keeps coverage high; the quick relevance check and scoring still decide relevance. Distances ("within 50 km") need map data, which comes with Phase 2; until then a nearby town is only kept when its address names the place (Irish addresses name the county). |
| **EURES is not used**, although its search API works well | Its "Find a job" terms forbid automated extraction of vacancy data for further processing and allow API use only for EURES partner organisations. The owner wants no legal risk. |
| **UK Find a Job (DWP) is not used** | It refuses Jobcu's requests with a web-application firewall. Jobcu never works around bot protection. |
| **Community Employment scheme jobs count as part-time, apprenticeships and work placements as "internship or working student", self-employed as "freelance or contract"** | Closest matches among Jobcu's job types, the same mapping style as the Bundesagentur's. |

## 2026-09-17 (night): Company career systems, the employer directory and Arbeitnow

| Decision | Reason |
|---|---|
| **Company career systems are read from Phase 1 on** (Greenhouse, Lever, Ashby, Workable, Recruitee and Workday), through the public job lists those systems publish for career pages. This brings HANDOVER §9.3 forward from Phase 3. | Ireland's engineering jobs are mostly posted on companies' own career sites first, and Adzuna doesn't cover Ireland at all. Career-system ads are the original, earliest and most accurate version of a job. |
| **An employer directory ships with Jobcu** (`src/jobcu/data/employers.json`): the companies Jobcu knows, their career system and the supported countries they hire in. It's checked and refreshed with `tools/check_employers.py` (one request per company), from public career sites only, **never from anyone's searches**. | HANDOVER §9.3: career systems can't be searched across companies, so Jobcu needs a list. Keeping it general reference data keeps every search fresh and private. |
| **Only companies with jobs in the supported countries stay in the directory**, and each entry records whether the company also hires elsewhere. | Keeps searches short (no requests for companies that don't hire here) and lets Jobcu judge unclear locations: at a company that only hires in Ireland, "Head Office" is Ireland. |
| **A free-text location is turned into a country by `placenames.py`** (country names in English and local languages, regions, and the bigger towns, plus well-known places elsewhere). | Career systems give locations only as text. It also protects against "Dublin, CA" or "Cambridge, MA" being taken for the Irish or English ones. Real map data comes with the smart location filter in Phase 2. |
| **SmartRecruiters is not read** although its Posting API is public | Its robots.txt allows only LinkedIn's crawler. Jobcu respects robots.txt. |
| **Workday sites are read only after checking each site's robots.txt** | Workday's job list address isn't documented, so Jobcu asks each company's own site whether automated reading is allowed, and skips it if not. |
| **Arbeitnow is a source** (free public API, no key) | It carries jobs from career systems of hundreds of German and British companies that aren't in the directory, with full ad texts and exact posting times. Its terms allow free use and ask for a link back, which Jobcu's job link gives. |
| Companies whose own servers differ per company (Workday, Recruitee) are read **four at a time**; the polite pace per server is unchanged. | A search reads many companies; without this, big directories would make searches take much longer. Shared servers (Greenhouse, Lever, Ashby, Workable) are still read one request at a time. |
