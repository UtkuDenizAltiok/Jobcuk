# Job sources: facts learned from real tests

What Jobcu knows about each source, verified with real requests (dates are when it was checked).
Update this whenever a source changes or something new is learned. Decisions are in
[DECISIONS.md](DECISIONS.md).

## Adzuna (`src/jobcu/sources/adzuna.py`), checked 2026-09-17

- **Official API, free key** (Application ID + Application Key), entered in Settings.
- **Limits of a free key:** 25 requests a minute, 250 a day, 1,000 a week, 2,500 a month.
  Jobcu pauses 2.6 s between API requests and counts every request in the `source_requests`
  table (stops at 240 a day and 2,400 a month).
- **Countries:** AT, BE, CH, DE, ES, FR, GB, IT, NL, PL. **Not Ireland**, and no other supported
  country.
- **Query parameters that work:** `what_or` (any of these single words, space-separated),
  `what_phrase` (exact phrase), `what` (all words), `where` + `distance` (km), `max_days_old`,
  `sort_by=date` (newest first), `results_per_page` up to 50. Boolean queries like
  `"a" OR "b"` return **0 results**.
- **Answers:** exact posting time (`created`, UTC), company, location with coordinates, contract
  type/time, `redirect_url`. The description is only the **first ~500 characters**.
- **Full ads:** `redirect_url` leads to `www.adzuna.<country>/details/<id>`, which carries
  schema.org JobPosting JSON-LD with the full text. Read at a 3 s pace, only for jobs that passed
  the quick relevance check (owner's decision). **Some single ads answer 403 "Zugriff verweigert"**
  while others load: skip that ad; stop only after 3 refusals in a row or a robot check.
- Adzuna's website answered 403 to `robots.txt` and its terms page for Jobcu's User-Agent.
- Adzuna often lists the same job twice under different IDs.

## Reed (`src/jobcu/sources/reed.py`), checked 2026-09-17

- **Official API, free key** (the key is the Basic-auth user name, empty password). UK only.
- No published rate limit found; Jobcu pauses 0.5 s and caps itself at 400 requests per search.
- `GET /api/1.0/search`: `keywords`, `locationName`, `distanceFromLocation` (miles),
  `resultsToTake` (max 100), `resultsToSkip`. **No date filter, no date sorting, and `OR` doesn't
  work** (one request per search word, read every page).
- Posting date is **by day** (`date`, dd/mm/yyyy). Search results carry a short description.
- `GET /api/1.0/jobs/{id}`: full description (HTML), `contractType` (Permanent / Contract /
  Temporary), `fullTime`, `partTime`, salaries, `externalUrl` (often the employer's or an
  agency's application page).
- Many Reed ads come from recruitment agencies.

## Bundesagentur für Arbeit, Jobsuche (`src/jobcu/sources/bundesagentur.py`), checked 2026-09-17

- **No official API.** Public endpoint documented by github.com/bundesAPI/jobsuche-api; header
  `X-API-Key: jobboerse-jobsuche` (the public client ID the agency's own website uses). May change
  without notice.
- `GET .../jobsuche-service/pc/v6/jobs`: `was` (one phrase), `wo` + `umkreis` (km),
  `veroeffentlichtseit` (days: 0 = today, 1 = since yesterday), `size` (up to 100), `page`.
  Answer: `ergebnisliste`, `maxErgebnisse`.
- Each result has `referenznummer`, `stellenangebotsTitel`, `firma`, `stellenlokationen` (address
  and coordinates), **`datumErsteVeroeffentlichung`** (first publication date, by day),
  `vertragsdauer` (UNBEFRISTET / BEFRISTET), `arbeitszeitVollzeit`, `stellenangebotsart`
  (ARBEIT, SELBSTAENDIGKEIT, PRAKTIKUM_TRAINEE, AUSBILDUNG).
- `GET .../pc/v4/jobdetails/{base64(referenznummer)}`: full description
  (`stellenangebotsBeschreibung`), `allianzpartnerUrl` (often just the company homepage, so not
  used as a job link). Job page for people: `https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}`.
- **Also lists jobs abroad** (e.g. Austria): the country comes from `adresse.land` (German names).
- No rate limit found; Jobcu pauses 0.7 s.

## JobsIreland.ie (`src/jobcu/sources/jobsireland.py`), checked 2026-09-17

- The Irish public employment service's job board (Department of Social Protection). About
  5,100 open vacancies, roughly 300 new a day; many are care, retail, trades and Community
  Employment (CE) scheme placements, some engineering and technician jobs.
- **No API.** The browse page loads its list from
  `GET /Jobsireland.API/JobsIreland/BrowseJobs?keyWord=&location=&page=N&pageSize=100`
  (also `CareerlevelId`, `vacancyId`, `VacancyTypeId`, `ContractTypeId`, all empty). It answers
  **HTML**, sorted **newest first** by publish time; page size 100 works (the page offers 10–100).
  Each answer takes about 5 s.
- Each job block (`div.job-heading[data-vacancyid]`) has hidden inputs `JobId`, `JobTitle`,
  `Location` (often starts with the employer's name), `StartDate` (publish time, **Irish local
  time without a zone**, e.g. `2026-09-16T14:24:50`), `EndDate` (closing date), `VacancyTypeId`
  (0 paid position, 3 CE scheme, 4 apprenticeship, 6 self-employed, 10 WPEP work placement).
  The employer's name is only in the logo's `alt="Logo of …"`, and not always. `ul#longlats li`
  holds `lat;lon;address;title;id;ref`, several per job with several locations. The page also
  carries an empty template block (`#JobId`).
- **Keyword search looks at titles only** ("Azure" found nothing although it was in an ad's
  text), so Jobcu reads the newest pages and matches titles itself.
- Job page `GET /en-US/job-Details?id=N`: full ad in `<pre ng-bind-html="Description | linky">`,
  and a list `ul.job-detail_list` with employer, "39 hours per week", "37000.00 Euro Annually" or
  "30000.00 - 34500.00 Euro Annually", publish and closing dates. **No schema.org JobPosting, no
  permanent/temporary information.**
- **robots.txt allows everything.** Terms: the information "is intended only for use by
  jobseekers searching for suitable employment"; re-publishing or reproducing it needs the
  department's permission. Jobcu only shows jobs to the person searching, on their computer.
- Jobcu pauses 2 s between requests and reads at most 40 list pages per search.
- Many JobsIreland jobs also appear on EURES (IDs like `base64("2470780 18")`, 18 = JobsIreland),
  but EURES showed only ~1,970 of its ~5,100 jobs.

## Checked and not used

- **EURES** (europa.eu/eures), checked 2026-09-17. Technically ideal: `POST
  /eures/api/jv-searchengine/public/jv-search/search` returns full ads with exact creation times
  for all EU/EEA countries (max 50 per page; space-separated keywords mean OR, separate keyword
  entries mean AND; `publicationPeriod` LAST_DAY / LAST_THREE_DAYS / LAST_WEEK / LAST_MONTH;
  keyword codes EVERYWHERE / TITLE / DESCRIPTION / EMPLOYER; europa.eu robots.txt asks for a
  10 s crawl delay). **Not used:** the "Find a job" terms say users may not use "screen
  scraping" or any other automated system to extract vacancy data to process it further, and
  that only EURES partner organisations recognised by a National Coordination Office may extract
  data using the API. Its jobs come from public employment services Jobcu reads directly
  (Bundesagentur, JobsIreland) or may read later.
- **UK Find a Job (DWP)**, findajob.dwp.gov.uk, checked 2026-09-17. Requests with Jobcu's
  User-Agent time out, and a browser-like request gets a web-application-firewall page ("Something
  went wrong"). That's bot protection, so Jobcu doesn't use it.

## General observations

- In 815 real ads (Reed + Bundesagentur, one week, electronics roles), **employer links almost
  never pointed to company career systems** (Greenhouse, Personio, Workday and similar). They
  pointed to company homepages, staffing agencies (Ferchau, Brunel, Akkodis, Hays…) or other
  boards. Career systems therefore need the employer directory (Phase 3).
- German engineering ads include many from staffing agencies, often near-identical for different
  clients (see duplicate rules in `dedupe.py`).
