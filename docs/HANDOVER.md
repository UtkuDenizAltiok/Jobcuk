# Jobcu — Project Handover for Claude Code

> Written in a planning conversation between the owner and Claude (chat), September 2026.
> This document is the source of truth for everything decided so far.
> **You, Claude Code, are now the project owner, architect, designer and builder.**

---

## 0. Read this first

### Your role
You own this project end to end: tech stack, architecture, repository structure, UI design, implementation, testing and documentation.

- Items marked **Decided** come from the owner. Don't change them without asking him.
- Items marked **Suggestion**, or anything this document doesn't cover, are your call.

### Who you're working with
The owner will use the app and work with you. **He has zero knowledge of programming, software or app development.** Never assume he knows words like terminal, repository, commit, API, install, folder path or error log. Adjust how you work:

- **Plain language.** Explain what you're doing and why, in everyday words. If a technical word is unavoidable, explain it the first time.
- **Exact instructions, one step at a time.** When he has to do something himself (install a tool, create an API key, set up GitHub), say exactly where to click and what to type. He uses a MacBook. Confirm each step worked before giving the next one.
- **Errors:** if he pastes an error message, explain in simple words what went wrong and what to do.
- **Do the technical work yourself** whenever you can, instead of asking him to.
- **Ask before:** adding any paid service, changing a Decided item, or doing anything that affects his accounts or costs.
- **Decision log.** Keep `docs/DECISIONS.md` with each decision you make and a one-line reason, so he can follow the project.
- **Phases.** Work through the phases in section 16. Finish, test and show him each phase before starting the next.

### What the owner cares about most
He asked for the best possible app and trusts you with the details. When something isn't covered here, or two goals conflict, decide in this order:

1. **Never break the hard rules:** no logins on job sites (no account-ban risk), device-local only, macOS and Windows both, no provider recommendations.
2. **Don't miss relevant fresh jobs. This is Jobcu's main purpose.** Find as many available job postings from as many sources as possible (section 9.0); the newest jobs matter most; never show jobs proven to be too old.
3. **Accurate filtering and scoring** for the current CV, cover letter and location text.
4. **Simplicity** for a non-technical user.
5. **Reasonable cost:** up to **€30 a month** for the owner's own use; lower is better. Optimise cost, but never by lowering the quality of 2 and 3.
6. **Speed is not a priority.** A search may take several minutes; it just shouldn't take hours. Don't add cost or much complexity only to make searches faster.

---

## 1. The product in one paragraph

**Jobcu** is a job search app for **EU countries plus the UK, Switzerland, Norway and Iceland** (no other countries). The user provides three things:

1. their CV
2. a generic cover letter that explains who they are and what kind of job they want
3. a free-text description of where they want to work

When the user presses **Search**, the app:

- collects recent job postings from as many sources as possible
- removes duplicates
- applies the location criteria
- scores every job against the user's profile
- shows a ranked list with short reasons for each score

---

## 2. Users, platform and distribution — Decided

- **Users:** the owner and a few friends. **A private app only.** No website, no hosting, no server, no cloud storage, no user accounts — now or planned.
- **Platforms: macOS and Windows, both fully supported.** The owner uses a MacBook; friends may use Windows. Every feature, the launcher, file handling and the guides must work on both. Don't postpone Windows: set up automatic tests that run on both systems from the start.
- **Form:** a local web app. It runs on the user's own computer and is used through a normal browser.
- **Device-local only.** Each person installs the app on their own computer and uses it there with their own API keys, CVs, cover letters, searches and results.
  - nothing is shared or synchronised between users
  - no feature connects users or lets them see each other's data
- **Local storage only.** Each copy saves what it needs to remember (section 12) and its settings and keys in a data folder on that computer. This folder is separate from the app's code folder, so updating never erases it.
- **Network connections:** the app talks only to job sources and to the AI provider the user chose. No analytics, no telemetry, no connection to any server of ours.
- **Code:** a **private GitHub repository**. Friends get access so they can download the app and its updates. Only code and documentation live there, never anyone's data or keys. Explain to the owner how to give friends access so they can download without accidentally changing the code.
- **Updates:** users download the new version from GitHub; their data folder is kept.
- **Easy start:** a first-run setup screen for choosing an AI provider and entering API keys, and a double-click way to start the app on each platform.
- **UI language:** English only.

**Suggestion (your call):**
- Python backend (strong ecosystem for web requests, data handling and the AI providers' SDKs)
- SQLite local database
- a simple web frontend served locally

### 2.1 GitHub written for everyday people — Decided

Friends are not programmers. Someone who has never used GitHub must be able to understand, install and use the app from the repository alone.

- **README, first screen:** in plain words: what the app does, what you need (a Mac or Windows computer, an API key from any AI provider, free job-site keys), what it can cost, and that everything stays on your own computer. Then clear links to the guides.
- **Step-by-step guides with screenshots (in `docs/`):**
  - downloading the app from GitHub, for someone who has never used GitHub
  - installing and starting it on macOS, and on Windows
  - getting an AI API key from several common providers (neutral, no recommendation), and the free Adzuna and Reed keys
  - a walkthrough of a first search
  - understanding results: scores, reasons, "verified" and "AI estimate" labels, job buttons
  - costs and limits, and how to set a spending limit
  - updating without losing data, and uninstalling
  - troubleshooting and FAQ
- **No jargon.** If a technical word is unavoidable, explain it the first time.
- Keep the guides in step with the app, and test them by following them exactly on a clean computer.

---

## 3. Main user flow — Decided

1. **Inputs:** the user uploads a CV (PDF/DOCX) and a generic cover letter (PDF/DOCX/plain text) for the search.
2. **Search screen:**
   - CV and cover letter, with a "What the app understood" link (shows the profile and how the location text was understood)
   - "Where do you want to work?" free-text box
   - "Posted within" selector: 6 hours / 24 hours / 72 hours / 1 week
   - job type checkboxes
   - a "Don't include remote jobs" checkbox: when ticked, fully remote jobs are left out; hybrid and on-site jobs stay
   - **Search** button
   - a small "Search details" link
3. **Search runs only when the user presses Search.** No background or scheduled searches.
4. **Visible progress.** Show which sources are being checked and roughly how far along the search is, so the user knows it's working. A search taking several minutes is fine; hours is not. Checking sources in parallel and showing jobs as they arrive are nice to have: use them only if they don't raise cost or add much complexity.
5. **Results:** a ranked list of job cards (section 12).
6. **Every search starts fresh** from the current CV, cover letter and location text. Only the items in section 12 carry over.

The owner approved a sketch of this layout: search panel on top, results summary line ("38 jobs found, 12 new since your last search"), job cards below.

---

## 4. Candidate profile — Decided

- At the start of **every search**, the AI reads the current CV and cover letter and produces a structured profile.
- **Do NOT rate, grade, critique or rewrite the CV or cover letter.** The goal is only to understand the person and what they want.

Suggested profile fields:
- current or most recent role and field
- skills and technical areas
- years of experience and seniority level
- education
- languages, with levels (CEFR where possible)
- target roles and fields
- preferences stated in the cover letter (industry, company type, remote/hybrid, etc.)
- dealbreakers, if stated
- work authorisation or citizenship, **only if the user provides it** (in the CV, cover letter or location text)

How the profile is handled:
- The profile is used only for that search and is not kept for later searches.
- The user can open "What the app understood" to see it; no review step is required.
- **Never guess** nationality, gender, age or similar from a name, university or anything else.

---

## 5. Search words (hidden) — Decided

Job sources can't read a CV; they need text queries. The app therefore generates search words automatically.

- The AI derives job-title and skill keywords from the profile.
- Keywords are created **in English plus the local languages of the countries being searched**. For example, a German search should include German job titles, or German-language ads will be missed.
- Include common title variants for the same role.
- **The user never has to see or type these.** The "Search details" link can show them, with per-source result counts, for troubleshooting.
- Generated fresh for every search.

---

## 6. Smart location filter — Decided concept, you design the details

The user types anything into the location box. Use the owner's own examples as test cases:

| Input | Expected behaviour |
|---|---|
| "London", "Munich", "Amsterdam", "UK", "Ireland", "Germany", "Belgium" | Direct place/country filter |
| "A city by the seaside" | Coastal places only |
| "A country where mostly English is spoken" | UK, Ireland, Malta |
| "A country that can give me dual citizenship within 10 years, I am [nationality]" | Country-level rule: verified from current official sources if possible, otherwise AI estimate with a warning |
| "A city with at least 300,000 people within a 30 km radius" | Freising **passes** (Munich is nearby); Warstein **fails** (no such city within 30 km) |
| "UK, but the company must be able to sponsor me" | UK jobs at companies on the UK sponsor register |
| "Germany, but the city must have a lower AfD vote share than the German average" | German places with below-average AfD result |

### Required design

1. **Interpret at the start of each search.** A capable model turns the sentence into structured criteria, for example JSON describing:
   - the targeted countries and regions
   - place conditions
   - company conditions
   - job conditions
   - whether each criterion is strict or preferred

   This interpretation also decides **which countries the sources are queried for**, because most sources are searched per country.
   - **If the user names countries or places** (e.g. "Germany, Ireland, UK"), only those are searched.
   - If the text doesn't limit countries (e.g. "a city by the seaside"), all supported countries are considered.
2. **Show the interpretation in plain English at the top of the results** ("Understood as: …"), without making the user confirm it before the search starts. An "Edit" option lets the user correct it and re-apply the filter to the jobs already found.
   - **Distances** like "within 30 km of a city" are measured to the nearest edge of that city's boundary, not its centre. This matches the owner's example: Freising is about 30 km from central Munich but much closer to Munich's city border, and it should pass.
3. **Evaluate each criterion at the right level:**
   - **Country:** languages, naturalisation and dual-citizenship rules
   - **Place:** population, nearby cities, coastline, election results
   - **Company:** e.g. on the UK sponsor register
   - **Job:** remote/hybrid, text saying "no visa sponsorship"
4. **Use real data wherever possible.** The AI should not judge every job location from scratch. Public reference data (populations, boundaries, sponsor register, election results) can be stored locally; it describes places and companies, not the user.
5. **Verified → hide; not provable → warn.**
   - A criterion counts as **verified** when it's checked against official datasets, or against current reliable sources found through real-time web search (e.g. an official government page). Keep the source link.
   - Jobs that **fail a verified criterion are hidden.**
   - When the answer **can't be proven** with current data and is only the AI's best guess, the job is **shown with a warning** ("AI estimate — please check").
6. **Each job card shows which location criteria it met**, marked "verified" (with source link) or "AI estimate".
7. **Unclear job locations** ("Germany", "multiple locations", "remote"): mark them "location unclear" instead of dropping them.
8. **Broad requests** (e.g. seaside anywhere in the EU) mean many countries, many queries and more cost. Warn the user and apply sensible caps.

### Candidate datasets (verify licence, freshness and format before using)

- **GeoNames:** places with coordinates and population.
- **Eurostat GISCO:** administrative boundaries (LAU/NUTS). Useful for distance to a city boundary and for mapping a place to its district.
- **Natural Earth or similar:** coastlines, for "seaside".
- **GOV.UK "Register of worker and temporary worker licensed sponsors":** official list of UK employers that can sponsor visas.
  - Company matching must be fuzzy, because legal names differ from brand names.
  - Being on the register doesn't mean this specific job offers sponsorship, so also check the job text.
- **Germany's Federal Returning Officer (Bundeswahlleiterin):** official Bundestag election results by constituency/district, for vote-share criteria.
- **Small maintained tables** for simple country facts (official languages, etc.).
- **Citizenship and naturalisation rules:** no single dataset, and rules change. First try to verify with real-time web search of official government sources; if that gives a clear, current answer, treat it as verified. Otherwise use an AI estimate with a warning.

---

## 7. Time filter — Decided

- Options: **last 6 hours, 24 hours, 72 hours, 1 week (168 hours)**, counted back from the moment Search is pressed.
- **Freshness is a top priority.** The owner wants to see jobs as soon as possible after they're posted. In his experience, jobs older than about a week are usually already filled, and applying early matters.
- **Get the freshest results from each source:** use each source's own date filter and newest-first sorting where available, and prefer sources that give exact posting timestamps (official job APIs, company career systems, job board listing pages).
- **Find the real first-posted date:** posting dates are messy (reposts look new, some sources give only a day, some say "30+ days"). So:
  - use the source's date; if it's missing or vague, open the job page and read the date there
  - compare all duplicate copies of the job and use the **earliest** date, which catches reposted old jobs
  - never trust an AI summary of a date; read it from the source itself
- **Same rule as location criteria:** if the job is **proven** to be older than the chosen time window, **hide it**. If the posting date **can't be determined**, don't hide it, but list it in a separate section **below** the main results, titled "Posting date unknown", so the main list only contains jobs confirmed to be fresh.
- Show the posting time clearly on every card (e.g. "posted 3 hours ago").

---

## 8. Job types — Decided

- Checklist on the search screen, chosen by the user: **Full-time permanent, Fixed-term, Part-time, Internship or working student, Freelance/contract.**
- If a source doesn't state the type, the AI infers it from the description. If it's still unknown, mark it "type unclear" rather than excluding the job.

---

## 9. Job sources

### 9.0 Coverage goal — the most important feature (Decided)

**Jobcu's main purpose is to find as many of the available, fresh, relevant job postings as possible, from as many sources as possible.** No app can reach literally 100% (some sites block automated access, and some jobs are never published publicly), but Jobcu should get as close as realistically possible, and **measure** how close it gets.

**How to maximise coverage:**
1. **Source registry.** Build and maintain a registry of sources for **every supported country** (EU countries, UK, Switzerland, Norway, Iceland). For each source record: country, type, access method, what it covers and its current status. Cover all source types in 9.2–9.7, not just the examples named there.
2. **Query each source thoroughly:**
   - use the multilingual search words and title variants (section 5)
   - go through **all result pages** within the time window, not just the first page
   - if a source caps results per query, split the query (by region, city or a shorter time window) so nothing is cut off
   - use the source's own location and date filters where they exist
3. **Read job pages generically.** Many career pages and job boards embed standard job data in the page (schema.org `JobPosting`, including `datePosted`). Read it wherever available: it works for sites without a dedicated adapter, and gives reliable titles, locations and posting dates.
4. **Combine discovery methods** so jobs missed by one route are found by another: direct sources, company career systems, the employer directory (9.3) and live AI web search (9.6).
5. **Measure coverage with a coverage test** (build it alongside the quality test in section 13):
   - for a few realistic test searches, the owner collects jobs he finds manually on LinkedIn, StepStone, Indeed and company sites
   - check what share of them Jobcu found, and why any were missed
   - fix the biggest gaps first; repeat after major changes
6. **Measure each source's value.** "Search details" shows, per source: jobs found, jobs found **only** by that source, and errors. Use this to decide where adding or fixing sources helps most.

Fetching job listings costs no AI tokens; AI cost comes from reading and scoring jobs. So wide coverage is compatible with the budget thanks to the free rule-based filters and the cheap first pass (section 13).

### 9.1 Policy — Decided

- **No logins anywhere.** No accounts, no user cookies, no credentials for any job site. The app must never be able to get anyone's account banned.
- **Within that rule, maximise coverage** using publicly accessible data.
- **Be polite:**
  - reasonable request volume, delays, caching within a search
  - back off on errors, respect `Retry-After`
- **Never try to bypass CAPTCHAs, logins or bot protection.** If a site blocks the app, back off and mark that source unavailable for this search.
- **Isolated adapters.** Each source is an independent module behind a common interface. **A failing source must never break a search.**
- **Visible source status.** Results show a status line per source (e.g. "StepStone: 23 jobs", "Glassdoor: unavailable").
- **Settings:** each source can be switched on or off; all are on by default.
- **Verify first.** Before building each adapter, check that source's current API or endpoint availability, terms and rate limits.
- **Job-alert emails: explicitly rejected by the owner. Don't build this.**

### 9.2 Official and open job APIs

- **Adzuna:** official API, free key with daily call limits (check current limits). Queried per country; covers the UK and several EU countries (verify which).
- **Bundesagentur für Arbeit (Jobsuche):** Germany's largest job database. There is no official API, but a public endpoint is documented by the community project `github.com/bundesAPI/jobsuche-api`. It may change without notice.
- **Reed:** UK, official API with a free key.
- **EURES:** the EU and EEA job mobility portal.
- **National public employment services** of every supported country that offer open job data. Candidates to check include Sweden's Arbetsförmedlingen (JobTech), Norway's NAV Arbeidsplassen, Switzerland's Job-Room, France Travail, Austria's AMS, Belgium's VDAB/Actiris/Forem, the Netherlands' UWV, Denmark's Jobnet and the UK's Find a Job service.
- **Aggregators with APIs:** Jooble, Careerjet, Arbeitnow and similar.

### 9.3 Company career systems (ATS) and employer directory

**Systems:** Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters, Personio, Workday, Teamtailor, JOIN, SAP SuccessFactors, Softgarden, d.vinci, Oracle Taleo, iCIMS, Jobvite and other systems common in the supported countries.

- These publish job lists per company. They are usually the original, most accurate and earliest source.
- **They can't be searched globally**, so companies are found in three ways:
  - companies seen in other sources in the same search (detect the career system from apply links)
  - live AI web search for career pages that match the role and target locations
  - **an employer directory shipped with the app:** a reference list of employers in the supported countries and the career systems they use, built from public sources and refreshed with app updates. It is general reference data, **never built from anyone's searches**, so every search still starts fresh. Each search picks the employers relevant to that search's countries and field.
- Companies with their own career pages (no known system) are read through the generic `JobPosting` reader (9.0).
- **Workday** endpoints are undocumented and differ per company, so they need extra care, but large employers often use Workday, so don't skip them.

### 9.4 Major and national job boards, public pages only

**Sites:** LinkedIn, Indeed, Glassdoor, StepStone, Xing, Totaljobs, IrishJobs, mamgo, plus the leading boards of **each** supported country. Candidates to check include CV-Library and Guardian Jobs (UK), Jobs.ie (Ireland), jobs.ch and jobup.ch (Switzerland), karriere.at (Austria), FINN.no (Norway), Jobindex (Denmark), Duunitori (Finland), Nationale Vacaturebank (Netherlands), APEC, HelloWork and Welcome to the Jungle (France), InfoJobs (Spain and Italy), Pracuj.pl (Poland) and Jobs.cz (Czechia).

- **Route A — AI web search:** use the chosen AI provider's web search tool to find these sites' public job pages, then read those public pages.
- **Route B — direct public-page readers:** read their publicly accessible, logged-out job listing pages.
- **Caveats (the owner understands and accepts these):**
  - **Terms of service:** most of these sites forbid automated collection even without logging in. The owner accepts this grey area for personal use, but **not** any account risk. Hence: no logins, ever.
  - **Bot protection:** some sites have strong protection. If an adapter can't work reliably without bypassing it, drop that adapter and note why in `docs/DECISIONS.md`. Jobs from those sites are then reached through other routes (company pages, aggregators, web search).
  - **Delay:** search engines index new pages hours or days late, so Route A adds little for the 6-hour filter.
  - **Breakage:** expect these adapters to break. Make them easy to fix and log failures clearly.

### 9.5 Recruitment agencies and specialist boards

- **Recruitment and staffing agencies** with public job listings (large international and national agencies).
- **Specialist boards** relevant to the user's field, found per search (e.g. engineering, IT, research such as EURAXESS, startups, universities and research institutes).

### 9.6 General live web search

- Use AI web search to find jobs anywhere else: company career pages, niche or regional boards, and so on.
- **Web search is for finding jobs, not for trusting details.** Search engines can be hours or days behind, and AI summaries can get dates and details wrong. Always open each job page found and read the real title, company, location and posting date before showing it (section 7).
- Web searches can cost money, so there's an adjustable cap per search run (section 13). When it's reached, the app asks before continuing.

---

## 10. Duplicates and the main link — Decided

- **One card per real job**, even if it's posted in several places.
- **Matching:** compare normalised company name, job title and location, plus description similarity. Use the AI only for uncertain pairs.
- **Main link priority:**
  1. the employer's own career page or ATS posting
  2. LinkedIn
  3. major job boards (StepStone, Indeed, Totaljobs, Xing, Glassdoor, IrishJobs, …)
  4. aggregators (Adzuna, etc.)
- The card shows "Also on: …" with links to the other copies.
- Agency reposts that hide the employer ("leading automotive company, Munich") are tagged **"possible duplicate"** instead of being merged automatically.

---

## 11. Scoring — Decided

### Pipeline
1. **Rules pre-filter (no AI, free), objective facts only:** jobs marked Not interested, proven older than the time window, a job type the user didn't select, fully remote when remote is excluded, or failing a verified location criterion. Don't judge the field or relevance with simple rules; that's the AI's job (section 13, quick first pass).
2. **AI scoring:** score the remaining jobs with a fixed rubric and structured output.

### Rubric (0–100)

| Component | Points | What it measures |
|---|---|---|
| Role and skills fit | 40 | How well the job's field, tasks and required skills match the profile |
| Seniority fit | 20 | Required years and level vs the user's |
| Language requirements | 15 | Required languages and levels vs the user's (e.g. German C1 required, user has B1) |
| Hard requirements | 15 | Work permit or sponsorship, security clearance, driving licence, specific degrees or certifications |
| Location and preference fit | 10 | Fit with the location criteria and with preferences from the cover letter (remote/hybrid, industry, etc.) |

### Rules
- **Low scores rank lower but are never hidden.** A junior can apply to a senior role; someone with basic German can apply to a German-required role. These jobs just score lower.
- Each card shows **1–3 short reasons**, e.g. "Strong skills match · Asks for 5+ years · German C1 required".
- "Search details" shows how many jobs were left out at each step and why, so nothing disappears unexplained.
- Freshness is **not** part of the score; it's handled by the filter and an optional sort.
- **Every search scores fresh.** Nothing learns or adapts from earlier searches.
- Token-saving rules for scoring are in section 13.
- **Model:** whatever the user chose in settings (section 13).

---

## 12. Results screen and job states — Decided

**Sorting:** by score by default, with newer jobs first when scores are equal; one click to sort by newest.

**Each job card shows:**
- score
- title and a "New" badge
- company
- location and work mode (remote/hybrid/on-site)
- job type
- posting time
- 1–3 scoring reasons
- location-criteria results, labelled verified or AI estimate
- main link and "Also on" links
- the three state buttons below

**Job states:**
- **Save**, **Applied** and **Not interested** buttons
- **Not interested jobs never appear again** in any later search, whatever CV, cover letter or location is used. A "Show hidden" toggle lets mistakes be undone.
- views or filters for Saved and Applied jobs
- **"New" badge:** the job hasn't appeared in any earlier search on this computer
- **Jobs shown before but not dismissed appear again normally** in later searches, just without the "New" badge. Saved or Applied jobs show that label when they reappear.

### What the app remembers between searches — Decided
- **Remembered (on this computer only):** jobs marked Not interested, Saved or Applied; which jobs have been shown before (for the "New" badge); settings and API keys.
- **Everything else starts fresh each search:** reading the CV and cover letter, search words, location interpretation, company discovery, scores.
- **Duplicates never show twice:** the same job from several sites is always one card (section 10). If any copy of a job was marked Not interested, all copies stay hidden.

**Search details:** the hidden search words, per-source counts and source status.

**Not in version 1:** Excel export.

---

## 13. AI providers, tokens and cost — Decided

### Universal provider support
- **Each user picks their own AI provider and model in settings. The app does not recommend, prefer or default to any provider**, in the UI or in the documentation.
- **Universal:** any provider should work. Build an internal AI layer with adapters for the common API formats:
  - the major native APIs (Google Gemini, OpenAI, Anthropic)
  - a generic **OpenAI-compatible** option (base URL + API key + model name), which covers many other providers and self-hosted models
- All AI calls go through this one layer, so switching provider is a settings change, not a code change.
- **Model names are entered or picked in settings, never hard-coded.** Providers rename and retire models often.
- **Simple by default:** the user picks one model for everything. An optional advanced setting allows a second model for the few reasoning-heavy steps (reading the CV and cover letter, interpreting the location text, AI estimates).
- **Setup check:** when a key and model are entered, run a quick test that the connection works and the model returns valid structured output. Show a plain message if it doesn't.
- **Differences between providers are handled gracefully:**
  - **Web search:** use the provider's built-in real-time search tool if it has one (e.g. Grounding with Google Search on Gemini, or the web search tools of OpenAI and Anthropic). **The app switches it on automatically; the user never configures it.** A simple "Use live web search" setting (on by default) lets them turn it off. If the provider requires billing or a plan upgrade for this tool, show a plain message explaining that. If the provider has no such tool, the web-search parts of a search switch off with a plain note ("AI web search isn't available with this provider"); everything else still works.
  - **Rate limits and free tiers:** on a limit error (e.g. HTTP 429), slow down and retry automatically without losing progress, and show a plain message ("AI limit reached, continuing more slowly" / "Daily AI limit used up").
  - **Structured output:** use the provider's native JSON/structured-output mode when available; otherwise validate and repair responses.
- **Documentation stays neutral:** the guides explain how to get a key from several common providers and how free and paid options generally differ, without recommending one.

### Quality first, then token optimisation — your responsibility
**Search quality and scoring quality come first.** The owner wants the app to search as widely as possible and to score as accurately as possible. Save tokens only where it doesn't change the results. Every search still starts fresh from the current CV, cover letter and location text, uses all sources, and scores every shown job with reasons.

**Quality test set (build early):** 30–50 real job ads, with the owner's own judgement of each (good / okay / poor fit, and any hard blockers such as language or visa). Use it to tune the scoring prompt, and to check every optimisation below with the model the owner is using. **If an optimisation makes the scores or the kept/dropped jobs meaningfully worse than without it, don't use it, or make it smaller.**

**Scoring quality:**
- Give the model clear point guidelines for each rubric component and a few worked examples, so scores are consistent and well reasoned.
- Read the CV and cover letter carefully at the start of each search (the optional second model from above can be used for this).
- Use the lowest reasoning or "thinking" setting that doesn't reduce quality on the test set, not simply the lowest available.

**Token savings that don't reduce quality:**
1. **Code before AI.** Do everything deterministic without AI: parsing source results, exact duplicate matching, date and job-type filters when stated, distance/population/sponsor-register checks from datasets.
2. **Merge duplicates before scoring,** so each real job is scored once per search.
3. **Remove dismissed jobs before any AI step.**
4. **Check place and company facts once per search.** Population, coastline, election results or sponsor-register status are the same for every job in that place or at that company, so checking once gives exactly the same answer. **Anything written in the individual job ad** (e.g. "no visa sponsorship", remote/hybrid, required languages) **is still checked for each job.**

**Savings that must pass the quality test before use:**
5. **Quick first pass:** a cheap check on the title, company and opening part of each ad may drop only **clearly** irrelevant jobs. When in doubt, keep the job for full scoring.
6. **Batch scoring:** several jobs per request can save tokens, but models can mix up or compare jobs in a batch. Start with small batches (3–5 jobs), instruct the model to score each job independently against the rubric, and validate every result. If batch scores differ meaningfully from one-job-per-request scores on the test set, use smaller batches or score one job per request.
7. **Cleaning job texts:** remove only text that can't affect scoring: legal disclaimers, equal-opportunity statements, cookie and navigation text, repeated text. **Keep** everything about tasks, requirements, languages, location, remote work, contract type, salary, and benefits such as relocation or visa support.
8. **Provider-side prompt caching** within a search, where the provider supports it.
9. **Short structured outputs:** scores and 1–3 clear reasons.

**Caps never silently reduce coverage.** When the per-search scoring cap or the web-search cap is reached, the app shows how many jobs or searches remain and asks the user whether to continue. Both caps are adjustable in settings.

**Measure it:** "Search details" shows the real tokens used per step, so quality and cost can be checked with real searches.

### Owner's budget
- **Up to €30 a month** for his own use; lower is better.
- Stay within it **without lowering search or scoring quality.** If real measured usage would cost more than that, tell him with the actual numbers and his options. Never quietly reduce quality to save money.
- Because speed isn't a priority, slower but cheaper processing options offered by the provider may be used, as long as a search still finishes in minutes, not hours.

### Planning numbers (rough, before the optimisations above)
- Heavy use of 5 searches a day, about 100 scored jobs and 10 AI web searches per search: roughly **180,000 input and 27,000 output tokens per search**, scoring being most of it.
- Actual money cost depends entirely on the model each user picks. Some providers also charge per web search.

### Cost controls (required)
- a usage meter per search and per month: always show tokens; show an estimated money cost when the model's price is known (a small editable price table in settings)
- an optional monthly limit the user sets; stop AI work when it's reached
- the scoring cap and web-search cap above (they ask before stopping; they never silently skip jobs)

---

## 14. Privacy and security — Decided

- All user data (documents, profiles, jobs, job states, caches, settings) stays **in the local data folder on the user's computer**.
- API keys are stored locally (in the data folder or the OS keychain), **never in the git repository**. Set up `.gitignore` in the first commit, and add a safeguard against committing secrets.
- **The repository must never contain keys, CVs or any user data.** Add an automatic check that blocks committing them.
- Never commit real CVs or personal data. Tests use fake documents.
- The GitHub repository is private; the owner and invited friends have access.

### 14.1 Protecting Jobcu as the owner's work — Decided

**Private repository, always.**
- The repository stays private. Never make it public, and don't publish Jobcu's code or documents anywhere else.
- Friends get download-only access, so they can use and update the app but can't change the code. Walk the owner through setting this up.

**"All rights reserved" notice.**
- Add a `LICENSE` file in the first commit, with a proprietary notice along these lines:
  > Copyright © 2026 Utku Deniz Altiok. All rights reserved.
  > Jobcu, including its source code, design and documentation, is the property of the copyright holder. No part of it may be copied, modified, distributed, published or sold without the owner's written permission. People the owner has invited may download and use Jobcu for their own personal use.
- Confirm the exact name spelling with the owner before committing.
- Add one short line at the bottom of the README pointing to the `LICENSE` file, and show "© Utku Deniz Altiok. All rights reserved." on the app's About or settings screen.
- Keep the wording friendly and simple. No agreements or signatures for friends.

**Dated records of the owner's work.**
- Put this handover file into the repository in the **first commit** (e.g. `docs/HANDOVER.md`) as the original, dated concept document. Keep it; record later changes in new commits instead of replacing its history.
- **Never rewrite or delete the repository history** (no force-pushing, no squashing away old commits). Commit timestamps are the dated record of how and when Jobcu was created.
- Keep dated entries in `docs/DECISIONS.md`.
- Show the owner how to download a full backup copy of the repository and keep it on his own computer or storage, e.g. after each finished phase.

---

## 15. Out of scope

- a website, hosting, a server, cloud storage, user accounts, or open-sourcing
- any sharing of data between users, or features that connect users
- learning from or adapting to past searches (beyond what section 12 remembers)
- background or scheduled searches, and notifications
- job-alert email reading
- logging into any job site; auto-applying
- rating or rewriting CVs and cover letters
- Excel export
- countries outside the supported list (EU countries, UK, Switzerland, Norway, Iceland)
- non-English UI

---

## 16. Phased plan (suggestion — agree the details with the owner)

**Phase 0 — Foundations**
- Explain the plan and chosen tech stack to the owner in plain language.
- Guide him step by step through:
  - installing prerequisites on his Mac
  - creating the private GitHub repo
  - getting an API key from the AI provider he chooses, and free Adzuna and Reed keys
- Create the project skeleton, `.gitignore`, secrets handling, the separate local data folder, `docs/DECISIONS.md`, a first plain-language README, the `LICENSE` notice and `docs/HANDOVER.md` (section 14.1).
- **Done when:** the app starts on his Mac with one action and shows an empty screen.

**Phase 1 — Usable first version**
- the universal AI provider layer (section 13), including rate-limit handling and the setup check
- CV and cover letter upload, and reading them fresh for each search
- simple location input (explicit places and countries)
- time filter and job type filter
- hidden multilingual search words
- starter sources: Adzuna, Bundesagentur, Reed, and a starter set of company career systems
- duplicate detection with main-link priority
- the quality test set (section 13) and a tuned scoring prompt
- scoring with reasons
- results screen with job states
- usage meter and caps (section 13)
- **Done when:** the owner can run a real search on his Mac and get a ranked, deduplicated list with reasons.

**Phase 2 — Smart location filter**
- location interpretation shown with the results, with an Edit option
- datasets from section 6
- **Done when:** all example sentences from section 6 behave as described.

**Phase 3 — Maximum coverage**
- source registry for every supported country (section 9.0)
- all source types from sections 9.2–9.6, including the generic `JobPosting` reader, more career systems and the employer directory
- general live AI web search
- per-source status, unique-job counts and on/off settings
- **Done when:** the coverage test (section 9.0) shows no large avoidable gaps, and the remaining gaps are explained to the owner.

**Phase 4 — Ready for friends**
- a full manual test on a real Windows computer and a real Mac
- the complete everyday-user documentation from section 2.1, tested on a clean Mac and a clean Windows computer
- first-run setup screen (choose provider, enter keys) and double-click launchers
- updating from GitHub while keeping the user's data folder
- confirm the check that blocks keys and personal data from the repository

---

## 17. Owner's answers to earlier open questions

**Answered by the owner:**
- **Countries:** EU countries plus the UK, Switzerland, Norway and Iceland. If the user names specific countries, only those are searched.
- **App name:** Jobcu.
- **Remote jobs:** a simple "Don't include remote jobs" option on the search screen.
- **Verified vs AI estimate:** if a location criterion can be proven with official or current real-time data, jobs that fail it are hidden. If it can't be proven, jobs are shown with a warning. Posting dates follow the same idea: proven too old → hidden; unknown → shown in a separate section below the main results.

**No open questions remain.**
