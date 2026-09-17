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

## General observations

- In 815 real ads (Reed + Bundesagentur, one week, electronics roles), **employer links almost
  never pointed to company career systems** (Greenhouse, Personio, Workday and similar). They
  pointed to company homepages, staffing agencies (Ferchau, Brunel, Akkodis, Hays…) or other
  boards. Career systems therefore need the employer directory (Phase 3).
- German engineering ads include many from staffing agencies, often near-identical for different
  clients (see duplicate rules in `dedupe.py`).
