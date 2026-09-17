# Jobcu progress

Jobcu is built in phases (see section 16 of [HANDOVER.md](HANDOVER.md)). Each phase is finished,
tested and shown to the owner before the next one starts. Decisions are in
[DECISIONS.md](DECISIONS.md).

## Right now

*Last updated: 2026-09-17, end of the first working session (before `/clear`).*

**Where we are:** Phase 1 (usable first version), most of it built. Everything is committed and
pushed, and GitHub's tests pass on macOS and Windows. A full check-up after an interrupted reply
found nothing lost or broken.

**Last finished:** tester-ready README and guides (install and start on Mac and Windows, first
search, troubleshooting), and Start Jobcu files that install the helper program uv themselves.
Before that: reading full ads from Adzuna's job pages (owner approved), employer's own page as
the main link, a full project check-up, the owner's guidance on usage and money
([DECISIONS.md](DECISIONS.md), "Owner's guidance on usage and money").

**Waiting on the owner (Utku):**
0. **Invite his friend as a tester:** add the friend's GitHub username under the repository's
   Settings → Collaborators, then send him the link to the README. The friend follows
   `docs/guides/install-and-start.md` → `getting-your-keys.md` → `first-search.md`. Collect the
   friend's feedback (installation problems, confusing steps, results quality).
1. **Step 4: run a real search himself** (double-click Start Jobcu → Search) and give feedback: do
   the top results look right, is anything scored too high or too low, were any titles "left out
   as clearly unrelated" (in Search details) actually relevant?
2. Optional, in his own time: a **generic cover letter**. The uploaded one is written for Tesla. The
   generic one should say he's open to any electronic hardware design field, with power electronics
   preferred and aerospace and defence also of interest.

**Next tasks for the assistant, in this order:**
1. **Adaptive Adzuna budget** (`sources/adzuna.py`, `sources/budget.py`): replace the fixed 40
   requests per search with a share of what's left this month, spread over the remaining days at
   about 3 searches a day. Never above what's left today, and roughly 25–60 per search. Test it.
2. **Usage meter and limits in Settings** (HANDOVER §13): AI tokens for the last search and this
   month, estimated cost from an editable price table (no prices built in), optional monthly
   token or cost limit (already enforced in `ai/client.py`), scoring limit, and job source on/off
   switches (`settings.sources_disabled` already exists). Also show Adzuna requests used
   today and this month.
3. **Score check / quality test set** (HANDOVER §13, owner chose "quick review"): collect about 40
   real ads from real searches (a mix of good, okay and poor fits). Claude pre-fills a rating for
   each (good / okay / poor, plus blockers such as language or visa). Build a simple review page
   in Jobcu where the owner corrects the ratings; store them in the data folder, never in the
   repository. Then measure Jobcu's scores against the ratings and check:
   - does the quick relevance check drop jobs he rates okay or good?
   - batch size 4 vs 1
   - short summary vs full ad
   - scoring reasoning effort

   Tune the scoring prompt, and record results and choices in DECISIONS.md.
4. Keep the guides in `docs/guides/` in step with every screen change, and fix whatever the
   friend's feedback shows is unclear.
5. Confirm Phase 1 "Done when" with the owner, update the README progress line, then plan
   Phase 2 (smart location filter, design choices already in DECISIONS.md).

**Useful facts:** source behaviour and limits are in [SOURCES.md](SOURCES.md).
- **Owner's data folder:** `~/Library/Application Support/Jobcu`, with keys `adzuna_app_id`,
  `adzuna_app_key`, `ai_gemini` and `reed_api_key`. He uses Google Gemini, model
  `gemini-3.8-flash`, on the free allowance with no billing.
- **Real search timing:** Munich or within 50 km, 72 hours ≈ 2.5 minutes. About 25 Adzuna API
  requests, about 20 job pages at 3 s each, and about 30,000 AI tokens.

---

| Phase | What it delivers | Status |
|---|---|---|
| 0. Foundations | Project set-up; Jobcu starts with a double-click | ✅ Done (2026-09-17) |
| 1. Usable first version | A real search with ranked, deduplicated results and reasons | 🔨 In progress |
| 2. Smart location filter | Understands sentences like "a city by the seaside" | Planned |
| 3. Maximum coverage | Many more job sources in every supported country | Planned |
| 4. Ready for friends | Complete guides, first-run setup, tested on real Mac and Windows computers | Planned |

---

## Phase 0: Foundations ✅

- [x] Plan and technology explained to the owner in plain language
- [x] Tools installed on the owner's Mac (uv, which also installs Python)
- [x] Private GitHub repository created
- [x] Owner's keys obtained (his own AI provider, Adzuna, Reed) and kept in his password manager,
      never in the project. Steps written up in [guides/getting-your-keys.md](guides/getting-your-keys.md)
- [x] Project skeleton, `.gitignore`, key storage, separate local data folder
- [x] `docs/DECISIONS.md`, plain-language README, `LICENSE` notice, `docs/HANDOVER.md`
- [x] Safety check that blocks keys and personal data (before each commit and on GitHub)
- [x] Automatic tests on macOS and Windows, including starting Jobcu with the real launchers
- [x] Instructions for friends and their AI coding assistants: [CONTRIBUTING.md](../CONTRIBUTING.md),
      [AGENTS.md](../AGENTS.md)
- [x] **Done when:** Jobcu starts on the owner's Mac with one double-click and shows an empty
      screen. Confirmed by the owner on 2026-09-17.
- Backups: the owner decided GitHub is enough (see DECISIONS.md)

## Phase 1: Usable first version 🔨

- [x] Universal AI provider layer: native Anthropic, Google Gemini and OpenAI, plus a generic
      OpenAI-compatible option; rate-limit handling; setup check (HANDOVER §13)
- [x] Settings screen: choose provider and model, enter keys (saved only on the computer),
      test the AI connection and the Adzuna and Reed keys
- [x] Owner entered his keys in Jobcu and all three tests pass (2026-09-17)
- [x] CV and cover letter upload (PDF, DOCX, TXT) and reading, with a "What Jobcu understood"
      preview of the profile (§3, §4)
- [x] First real test on the owner's own documents (2026-09-17): 8 seconds, about 5,500 tokens
- [x] Owner confirmed "What Jobcu understood" is right (2026-09-17). He is open to any field of
      electronic hardware design (power electronics preferred, aerospace and defence also of
      interest) and will put this in his generic cover letter
- [x] Search screen: location box, "Posted within", job types, "Don't include remote jobs",
      live progress, "What Jobcu understood" and "Search details" (§3)
- [x] Simple location input: explicit places and countries; other conditions shown as "not
      checked yet" until Phase 2 (§6)
- [x] Hidden multilingual search words: English plus the job-ad languages of the countries
      searched (§5). First real run: 73 search words in 4 languages, about 10 seconds
- [x] Time filter and job type filter applied to the jobs found (§7, §8)
- [x] Starter sources: Adzuna, Bundesagentur für Arbeit, Reed (§9). Company career systems moved to
      Phase 3 (see DECISIONS.md)
- [x] Duplicate detection with main-link priority, "Also on" and "possible duplicate" (§10)
- [x] Rules filter and quick relevance check, with counts and left-out titles in Search details
- [ ] Quality test set of 30–50 real job ads judged by the owner, and a tuned scoring prompt (§13)
- [x] Scoring with 1–3 reasons per job (§11). First real search (Munich, 72 hours): 46 ads,
      41 different jobs, 22 scored, under 2 minutes
- [x] Results screen with Save / Applied / Not interested, "New" badge, Saved and Applied lists,
      "Show hidden", sorting, "Posting date unknown" section (§12)
- [x] Owner decided Jobcu may read Adzuna's job pages for full ads; now 18+ of 22 jobs are scored
      from full ads in a real search
- [x] Scoring limit that asks before scoring more (§13)
- [ ] Usage meter (per search and per month), monthly limits and price table in Settings (§13)
- [ ] **Done when:** the owner can run a real search on his Mac and get a ranked, deduplicated list
      with reasons.

## Phase 2: Smart location filter

- [ ] Location interpretation shown with the results, with an Edit option
- [ ] Reference datasets from HANDOVER §6 (places, boundaries, coastlines, UK sponsor register,
      German election results, country facts)
- [ ] **Done when:** all example sentences in HANDOVER §6 behave as described.

## Phase 3: Maximum coverage

- [ ] Source registry for every supported country (§9.0)
- [ ] All source types from §9.2–9.6: more career systems and the employer directory (the generic
      `JobPosting` reader already exists since Phase 1 and reads Adzuna's job pages)
- [ ] General live AI web search
- [ ] Per-source status, unique-job counts and on/off settings
- [ ] **Done when:** the coverage test shows no large avoidable gaps, and the remaining gaps are
      explained to the owner.

## Phase 4: Ready for friends

- [ ] Full manual test on a real Windows computer and a real Mac
- [ ] Complete everyday-user guides (§2.1), tested on clean computers
- [ ] First-run setup screen and polished double-click launchers
- [ ] Updating from GitHub while keeping the data folder
- [ ] Move the repository to a free GitHub organization and invite friends, choosing with the owner
      how friends can contribute (see DECISIONS.md)
