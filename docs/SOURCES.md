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
  `what_phrase` (exact phrase), `what` (all words), `title_only` (all these words in the title,
  checked 2026-09-22), `where` + `distance` (km), `max_days_old` (whole days), `sort_by=date` or
  `relevance`, `results_per_page` up to 50. Every answer carries `count`, the total number of
  matches, so one request with `results_per_page=1` measures a query. Boolean queries like
  `"a" OR "b"` return **0 results**. Adzuna matches word stems: `title_only=Elektronik` also finds
  every "Elektroniker" (3,685 in three days).
- **How much a query brings (DE, 3 days, 2026-09-22):** the owner's single words anywhere
  6,459 ads, the same without "Inbetriebnahme" and "Wechselrichter" 337, `what_phrase`
  "Leistungselektronik" 184, `title_only` "Hardwareentwickler" 38. With titles in the title and
  specific words anywhere, a real 30-request run read 192 ads with 19 requests, 78% related
  (before: ~1,500 ads, ~7% related, budget used up before the precise searches ran).
- **Answers:** exact posting time (`created`, UTC), company, location with coordinates, contract
  type/time, `redirect_url`. The description is only the **first ~500 characters**.
- **Full ads:** `redirect_url` leads to `www.adzuna.<country>/details/<id>`, which carries
  schema.org JobPosting JSON-LD with the full text. Read at a 3 s pace, only for jobs that passed
  the quick relevance check (owner's decision). **Some single ads answer 403 "Zugriff verweigert"**
  while others load: skip that ad; stop only after 3 refusals in a row or a robot check.
- Adzuna's website answered 403 to `robots.txt` and its terms page for Jobcu's User-Agent.
- Adzuna often lists the same job twice under different IDs.
- **Single queries answer 5xx now and then** (503 on 2026-09-23, after Jobcu's three polite
  retries). One failing query leaves the source "partial"; three mean Adzuna is really down.
- **Newer ads without a town (checked 2026-09-22):** in 50 fresh German results, 34 had
  `location.area` `["Deutschland"]`, no coordinates, and a `redirect_url` of the form
  `www.adzuna.de/land/ad/<id>` (not `/details/`); that page answers 403 to Jobcu. Their text
  usually names the place ("am Standort in Wietmarschen-Lohne"), which the quick relevance check
  reads. The other 16 had a full `area` list and coordinates.
- German locations read "Unterhaching, München (Kreis)": the part marked **(Kreis)** is the
  district around a city, not the city, so `places.locate` uses it only when no town is named
  besides it (found in a real test, 2026-09-21: suburbs passed a "1 million people" condition).

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
- **Finding one job again (checked 2026-09-22):** the `arbeitgeber` filter returns nothing in
  v6 (even `arbeitgeber=Bayernwerk AG`). Search results carry the employer as `firma` and places
  as `stellenlokationen` (`adresse.ort`, `breite`, `laenge`); searching by title and matching
  `firma` found 5 of 42 town-less Adzuna jobs reliably.

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

## Company career systems (`src/jobcu/sources/careers.py` and one module per system), checked 2026-09-17 and 2026-09-21

Jobcu reads the job lists that companies publish in their career systems. Which companies are
read comes from the **employer directory** (`src/jobcu/data/employers.json`), kept up to date with
`tools/check_employers.py` (one request per company; it records the supported countries each
company had jobs in, and whether it also hires outside them).

| System | Address Jobcu reads | What it gives | Notes |
|---|---|---|---|
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/{board}/jobs`, full ad from `…/jobs/{id}` | title, location text, `first_published` (exact), `absolute_url` | Public Job Board API. robots.txt allows everything but `/embed/`. EU boards (`job-boards.eu.greenhouse.io`) are served by the same API host. The list has no ad text, so full ads are read per job. |
| Lever | `GET api.lever.co/v0/postings/{company}?mode=json` (EU: `api.eu.lever.co`) | full ad, `createdAt` (exact), **`country`** code, `workplaceType`, `commitment` | Public Postings API; robots.txt asks for 1 s between requests. One country code even for jobs in several places, so it's only trusted for single-place jobs. |
| Ashby | `GET api.ashbyhq.com/posting-api/job-board/{board}` | full ad, `publishedAt`, location plus `addressCountry`, `employmentType`, `workplaceType` | Public Job Postings API. Answers can be several MB for big companies. |
| Workable | `GET apply.workable.com/api/v1/widget/accounts/{board}`, full ad from `…/api/v2/accounts/{board}/jobs/{shortcode}` | title, city and country code, `published_on` (**day only**), `employment_type`, `telecommuting` | Public widget API; robots.txt allows everything. |
| Recruitee | `GET {board}.recruitee.com/api/offers/` | full ad, `published_at` (exact), places with `country_code`, `employment_type_code`, remote/hybrid | Public Careers Site API. Each company has its own address, so several are read at once. |
| SuccessFactors (added 2026-09-21) | `GET {host}/sitemap.xml`, then the job's page `{host}/job/…/{id}/` | Either an RSS job feed (SAP: full ad, place "Walldorf, DE, 69190", **no date**) or a sitemap of job addresses `/job/{Town}-{Title}-{postcode}/{id}/` (Schaeffler, Festo, SICK, KUKA, MTU, ZF and most others; every entry has the same `lastmod`). The job page carries `itemprop` data: `datePosted` ("Wed Sep 09 02:00:00 UTC 2026"), `streetAddress` ("Bühl, DE, 77815"), `title`, `hiringOrganization`, `description` | SAP's Career Site Builder. robots.txt normally closes `/services/` (SuccessFactors' own RSS search, so it isn't used) and allows the sitemap and job pages; Jobcu checks each company's robots.txt anyway. In a search only the pages whose title matches the search words are opened (Schaeffler: 3 requests in a live test). SAP's feed is 16 MB. Hitachi Energy's and Lenze's sitemaps weren't job lists. **Only sites whose job pages carry the date, place and ad text are in the directory** (SAP, Schaeffler, ZF, KUKA, Festo, Endress+Hauser). Danfoss, SICK, Vitesco and Wacker pages show only the title (the rest needs JavaScript), and MTU's job pages redirect elsewhere: left out for now. |
| Teamtailor (added 2026-09-21) | `GET {board}.teamtailor.com/jobs.rss`, or `{own domain}/jobs.rss` for companies with their own career-site address | RSS: full ad (HTML), `pubDate` (exact, with zone), `remoteStatus` (`none`/`onsite`, `hybrid`, `fully`, `temporary`), `tt:locations` with city and English country name, department, role | Every Teamtailor career site publishes this feed. robots.txt allows it for every crawler (only `/app/`, `/messages/`, `/jobs/internal/` and one AI crawler are closed) and declares `ai-train=no, ai-input=yes`: Jobcu doesn't train anything. No job type in the feed. Popular in Sweden, Norway, the UK and Ireland. |
| Workday | `POST {host}/wday/cxs/{tenant}/{site}/jobs` with `{"appliedFacets": …, "limit": 20, "offset": N, "searchText": ""}`, full ad from `GET {host}/wday/cxs/{tenant}/{site}{externalPath}` | title, `locationsText`, **relative** date ("Posted Today", "Posted 3 Days Ago", "Posted 30+ Days Ago"); the full ad has `startDate` (day), `timeType`, `remoteType` | Not documented, so Jobcu reads each site's robots.txt first and skips the company if it disallows these addresses. Newest first, 20 per page. The answer's filters give each country an ID, so Jobcu asks per searched country. |

- **Finding SuccessFactors sites** (2026-09-21): their robots.txt has the tell-tale
  `Disallow: /services/`, `/applybutton/`, `/talentcommunity/` lines. Probing `jobs.{company}.com`
  for 50 big German engineering employers found 13; `check_employers.py --only-new` kept 11,
  of which 6 have job pages with full data.
- **Finding employers for the directory** (2026-09-21): web searches such as
  `site:teamtailor.com jobs Dublin engineer` give a handful of companies each. Teamtailor links in
  Arbetsförmedlingen's open data are mostly Swedish care and service employers whose ads Jobcu
  already gets from Arbetsförmedlingen, so they weren't added.
- **SmartRecruiters is not used:** `api.smartrecruiters.com/robots.txt` allows only LinkedIn's
  crawler and disallows everyone else, although the Posting API itself is public.
- **Personio is not used yet:** the XML feed (`{company}.jobs.personio.de/xml`) is empty unless the
  company switches it on (checked on several companies), and the career pages need JavaScript.
  Many Personio jobs arrive through Arbeitnow instead.
- Career-system jobs count as the **employer's own ad**, so they win the main link (HANDOVER §10).

## Arbeitnow (`src/jobcu/sources/arbeitnow.py`), checked 2026-09-17

- **Free public API, no key:** `GET https://www.arbeitnow.com/api/job-board-api?page=N` (Germany
  and neighbours, 250 jobs a page) and `https://www.arbeitnow.co.uk/api/job-board-api` (UK, 100 a
  page). Jobs come **newest first** with `created_at` (exact), the **full ad text**, company,
  free-text location, `job_types`, `remote` and a link to the job's page there.
- Its jobs come mostly from career systems (Greenhouse, SmartRecruiters, JOIN, Teamtailor,
  Recruitee, Personio), so it reaches many German and British companies Jobcu has no directory
  entry for. About 200 new jobs a day on the German list.
- Terms: free to use, "please do not abuse", and a link back to Arbeitnow, which Jobcu's job link
  provides. robots.txt allows everything.
- Locations are free text ("Berlin", "London, Greater London, United Kingdom", "Remote - EMEA"),
  so the country comes from `placenames.py`.

## jobs.ac.uk (`src/jobcu/sources/jobsacuk.py`), checked 2026-09-17

- Universities, research institutes and related employers, mostly in the UK and Ireland: a kind of
  job Jobcu's other sources barely carry (research, technical and academic posts).
- **No API.** `GET /search/?keywords=…&sortOrder=1&pageSize=25&startIndex=N` gives HTML with the
  jobs **newest first** (`sortOrder=1`; 0 is relevance, 2 is closing date). Each result has the
  job's link (`/job/{ID}/{slug}`), title, department, employer, location, salary and
  "Date Placed: 27 Aug" (day and month, no year).
- Each job's own page carries **schema.org JobPosting**, so `jobposting.py` gives the full ad,
  the exact date, the employment type and remote status.
- **robots.txt** allows everything except `/job/feedback/` and `/enhanced/fp/`. The terms say
  material may be downloaded, printed and copied "for your own personal use" and not re-published,
  which is what Jobcu does.
- Jobcu pauses 1.5 s, reads at most 4 pages per search word, and stops when a page has only jobs
  older than the window. A real check (UK and Ireland, 72 hours, 4 search words): **156 jobs in 11
  requests, 16 seconds**.
- Some ads are outside the supported countries (Dubai, Hong Kong); the country comes from the
  location text through `placenames.py`. Jobcu only asks jobs.ac.uk when the UK or Ireland is
  searched: it lists a few jobs elsewhere in Europe, but not enough to spend requests on.

## EURAXESS (`src/jobcu/sources/euraxess.py`), checked 2026-09-17

- The European Commission's researcher portal: research jobs, PhD and postdoc positions at
  universities, institutes and research-heavy companies in every supported country (about 6,900
  open offers).
- **No API.** `GET /jobs/search?keywords=…&sort[name]=created&sort[direction]=DESC&page=N` gives
  HTML, 10 results a page, newest first. Each result has the country as a label, the organisation,
  "Posted on: 17 September 2026", the title with `/jobs/{id}`, a summary and the work locations.
- Job pages carry **no** schema.org JobPosting, so the full ad is read with `trafilatura`; the
  page also states "Type of Contract" and "Job Status", which give the job type.
- **robots.txt allows `/jobs/search`.** No rule against automated reading was found, and the
  Commission's legal notice allows reuse of its content with the source named. (This is different
  from EURES, whose "Find a job" terms allow extraction only for EURES partner organisations.)
  Jobcu pauses 2 s and stops as soon as a page has nothing inside the time window.
- A real check (Ireland, UK and Germany, 72 hours, 3 search words): 5 jobs in 9 requests, 18 s.
- **It asks Jobcu to slow down** when a search uses many words (a German search with 20 words got
  "429" after about 50 requests). Jobcu now pauses 4 s, uses the field words first (research ads
  are described by field, not job title), reads at most 12 words and 2 pages each, and stops at
  25 requests per search.

## Arbetsförmedlingen, Sweden (`src/jobcu/sources/jobtech.py`), checked 2026-09-21

- **Sweden's public employment service**, through its open **JobSearch API** (JobTech):
  `GET https://jobsearch.api.jobtechdev.se/search`. All ads in Platsbanken, Sweden's national
  job board, with the **full ad text**. Data licence **CC0**, **no key or registration**, no
  robots.txt, no stated rate limit (data.arbetsformedlingen.se/dataservice/jobsearch).
- Parameters used: `published-after` (minutes back, or a datetime), `published-before`,
  `sort=pubdate-desc`, `limit` (at most 100), `offset` (**at most 2,000**). Older ads are reached
  by asking again with `published-before` set to the oldest ad seen. The `X-Fields` header asks
  only for the fields Jobcu uses (0.55 MB per 100 ads instead of 1.3 MB).
- **About 1,600 new ads a day** (10,900 in a week, counted on 2026-09-21). A 24-hour search is
  about 16 requests; a week about 110.
- **Why Jobcu reads the whole window instead of using `q`:** the default "smart" free-text search
  treats "hardware engineer" as one occupation (2 hits in a week, against 18 with
  `x-feature-disable-smart-freetext: true` and `x-feature-freetext-bool-method: and`), and word
  search doesn't look inside Swedish compound words ("kraftelektronik" isn't found by
  "elektronik"). Jobcu's own matching finds words inside longer words.
- `publication_date` is **Swedish local time** without a zone. `workplace_address` gives city,
  municipality, county (`län`) and `coordinates` as **[longitude, latitude]** (about 96% have
  them). The distance filter `position` + `position.radius` returned nothing in a test, so Jobcu
  matches places itself. Ads abroad (country other than "Sverige") are skipped.
- Job types: `employment_type` "Tillsvidareanställning" = permanent; "Vanlig anställning" depends
  on `duration` ("Tills vidare" = permanent, a period = fixed-term); "Tidsbegränsad",
  "Säsongsanställning", "Sommarjobb" = fixed-term; "Behovsanställning" (called in when needed) =
  part-time; `working_hours_type` "Deltid" adds part-time.
- `application_details.url` mostly leads to the employer's own application system (Varbi,
  ReachMee, Visma Recruit, Teamtailor, Recruitee), so it is used as the employer's link.
- A real check (24 hours, 12 electronics search words): 3 jobs in 17 requests, 10 s.

## Google Maps, for travel times (`src/jobcu/travel.py`), checked 2026-09-21

Not a job source: used only for conditions like "at most 50 minutes by public transport to a
big city", and only with the user's own key (Settings → Travel times).

- **Routes API, Compute Route Matrix:** `POST routes.googleapis.com/distanceMatrix/v2:
  computeRouteMatrix`, headers `X-Goog-Api-Key` and `X-Goog-FieldMask:
  originIndex,destinationIndex,duration,condition`; origins and destinations as `latLng`;
  `travelMode` TRANSIT / DRIVE / WALK / BICYCLE; `departureTime` for transit and driving (Jobcu:
  next Tuesday 8:00 local time). The answer is a JSON list of elements with `duration` like
  `"1020s"` and `condition` `ROUTE_EXISTS`. **At most 100 elements per request for TRANSIT**
  (625 otherwise). Billed per element (origins × destinations). Jobcu's requests use no
  traffic-aware routing and no two-wheeler mode, so they are billed as Essentials (Pro starts with
  TRAFFIC_AWARE; checked 2026-09-22).
- **Places API is not used** (it was for a short while on 2026-09-21): looking up "{company},
  {town}" can find the wrong site of a company with several, so Jobcu stays with the place the
  job ad gives (the owner's decision).
- **Free monthly allowance (since March 2025, checked 2026-09-21):** Route Matrix Essentials
  10,000 elements, Pro 5,000 (traffic-aware routing, which Jobcu doesn't use); Places Text Search
  Essentials/Pro 5,000; Geocoding 10,000. Above that, about $5 per 1,000 route elements and
  $32 per 1,000 place look-ups. Google requires a billing account even for free use.
- Jobcu counts elements in `source_requests` (`google_maps_routes`) and stops at the monthly
  limit in Settings (9,000 by default), then uses AI estimates.
- **Storing answers (checked 2026-09-22, Maps Service Specific Terms):** for the Routes API,
  section 19.3 allows caching **only latitude and longitude values, for up to 30 days**. Travel
  durations may not be cached (only the Navigation Connect API allows that). So Jobcu keeps
  Google's minutes only inside the search that asked for them; the AI's own estimates are
  remembered for 30 days in `travel_memory`. The same terms (19.1, 19.2) allow using the answers
  without a Google map, but never with a non-Google map.
- The key goes only in a request header, never in an address, so it can't end up in a log.
- **The daily quota is counted in Pacific time (checked 2026-09-23):** searches on the evening
  of 22 September (297 elements) and at 02:00 on 23 September (37) fell in the same Google day
  and passed the 320 quota, which answers 429 "Quota exceeded … Route matrix elements per day".
  The owner's daily quota is now 450 (31 × 450 = 13,950, about $20 above the free 10,000 if
  Jobcu's own monthly stop ever failed, so still inside his €25).
- **Car trips take no departure time (checked 2026-09-22):** with `departureTime` and the default
  routing, Google answers 400 "Timestamp cannot be set for TRAFFIC_UNAWARE routing mode". A time
  would need `routingPreference` TRAFFIC_AWARE, which is billed as Pro. Public transport keeps its
  departure time.
- **First real answer (2026-09-22, the owner's key):** Freising town centre → Munich centre
  (Marienplatz), transit, Tuesday 8:00: 69 minutes. Door to door, so walking at both ends and
  changes are included; the train ride alone is 25–45 minutes.
- **Google-side stops (checked 2026-09-22):** Cloud Billing's spend caps (Preview) pause a
  service once a budget is reached, but only for the Gemini API, Vertex AI (Gemini Enterprise
  Agent Platform), Cloud Run and Cloud Run functions, **not Maps**: a Maps budget can only send
  emails. The Google-side stop for Maps is therefore a daily quota on the Routes API.
- **Setting it up (checked 2026-09-22):** with a European billing address, turning on the Routes
  API first asks to accept the Google Maps Platform EEA Terms of Service (type "Confirm"). For the
  Routes API they add one rule: its route descriptions and steps may not be used "With any Map".
  After enabling, Google creates a key named "Maps Platform API Key" that is allowed 35 Maps APIs;
  restrict it to the Routes API. The quota page (Google Maps Platform → Quotas → Routes API) has
  adjustable daily quotas "DistanceMatrix - ComputeRouteMatrix per-element quota per day" and
  "Directions - ComputeRoutes per request quota per day" (both unlimited by default).
  [EEA adjustments for the Routes API](https://developers.google.com/maps/comms/eea/routes).

## Google Gemini API billing, the owner's AI provider, checked 2026-09-22

Not a job source; recorded because the owner uses it and pays for it.

- **A project with billing turned on gets no free allowance:** every request is charged at paid
  prices, however small. The free tier applies only to projects without billing; a person can
  keep both kinds of project, each with its own key.
- **Prepay:** credits bought in advance in AI Studio (Billing page) are used up in near real
  time. At zero, every request fails with HTTP 402 until more credits are bought, unless
  auto-reload is on (with an optional monthly auto-charge limit).
- **Prices for `gemini-3.8-flash` (checked 2026-09-22):** $0.75 per million input tokens and $3.75
  per million output tokens until 31 December 2026, then $1.50 and $7.50. Grounding with Google
  Search: 5,000 free search queries a month shared by all Gemini 3.x models, then $14 per 1,000,
  billed per query the model runs (one request can run several).
- **Spend caps:** per project, either in AI Studio (Spend page → "Monthly spend cap") or as a
  Cloud Billing budget with "Spend cap enforcement" (one project, one service, monthly; alerts
  fixed at 50%, 80% and 100%). At the cap, the Gemini API is paused until the cap is lifted by
  hand. Since April 2026 every billing account also has a tier-wide monthly cap.
- AI Studio's own "Monthly spend cap" (Spend page) is shown separately: with a spend-cap budget
  set in Cloud Billing, it still shows no cap. One of the two is enough.
- Sources: [Cloud Billing spend caps](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps),
  [Gemini API billing](https://ai.google.dev/gemini-api/docs/billing).

## Job boards on hold: what their terms say (checked 2026-09-18 and 2026-09-21)

Facts for the owner's decision (DECISIONS.md, 2026-09-17: boards stay on hold until the coverage
test shows what Jobcu misses). Nothing is built for them. **All four belong to the Stepstone
Group**, so one written permission could cover them all.

- **robots.txt** of IrishJobs.ie, Jobs.ie, Totaljobs and StepStone.de allows the `/job/` and
  `/jobs/` pages for every crawler (2026-09-18).
- **IrishJobs.ie and Jobs.ie** (The Stepstone Group Ireland Recruit Ltd, same terms): 4.8.1 use
  the site "only … for lawful purposes when seeking employment", and never overload it; 4.8.2 and
  4.8.3 no use of the site or its Content "in competition with our business activities (as
  determined by us at our sole discretion)"; 4.5.2 "our prior written permission is required for
  any such use or removal of the Content"; 16 "Content … can be downloaded for personal
  non-commercial use". **No clause names robots, crawling or scraping.**
- **Totaljobs** (The Stepstone Group UK Ltd): 1.1 the site is "for the sole purpose of individuals
  looking for employment opportunities"; people "may use, print and download information from the
  site for these purposes only" and may not otherwise copy, transmit or distribute it; any other
  "unauthorised processing" is a material breach. **No clause names robots or scraping.**
- **StepStone.de** (The Stepstone Group GmbH, terms of 06.11.2025, a PDF linked from
  /e-recruiting/rechtliches/nutzungsbedingungen-bewerber/): 1.2 only for "die individuelle
  Arbeitssuche natürlicher Personen", no other commercial use; **4.3.4 forbids scraping or
  similar techniques to collect content "für einen anderen Zweck"**, to republish it or to use it
  other than for the intended purpose of the services; 13.2 (i) forbids using the platforms "für
  die Entwicklung anderer Dienstleistungen". Its `/agb` address answers 403 even in a browser.
- **Reading of these facts (not legal advice):** each allows a person to download ads for their
  own job search, and Jobcu does only that, on the person's own computer, without republishing.
  But none clearly allows automated reading: StepStone.de names scraping and "developing other
  services", and the Irish sites keep the final say on what counts as competition and ask for
  prior written permission. That is **not "clearly permitted"**, so under the owner's no-legal-risk
  rule they stay on hold. The clean route would be written permission from the Stepstone Group
  for personal, non-commercial, device-local use.

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
- **EURES-style aggregators needing a publisher website** (Jooble, Careerjet) are still open
  questions: their free keys are meant for websites showing their jobs, and Jobcu has no website.
  The owner decides whether to sign up.
- **publicjobs.ie** (Ireland's public service recruiter) and **UK Civil Service Jobs**, checked
  2026-09-17: both answer automated requests with a bot check instead of the page
  (publicjobs.ie serves an obfuscated JavaScript challenge, Civil Service Jobs a "Quick Check
  Needed" page). Jobcu never works around bot protection, so neither is used.
- **The Muse API**: public and documented, but registration is expected for real use and the jobs
  are mostly American. Kept as an option.
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
