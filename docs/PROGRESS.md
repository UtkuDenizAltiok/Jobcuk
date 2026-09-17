# Jobcu progress

Jobcu is built in phases (see section 16 of [HANDOVER.md](HANDOVER.md)). Each phase is finished,
tested and shown to the owner before the next one starts. Decisions are in
[DECISIONS.md](DECISIONS.md).

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
- [ ] CV and cover letter upload, read fresh at every search (§3, §4)
- [ ] Simple location input: explicit places and countries (§6)
- [ ] Time filter (6 h / 24 h / 72 h / 1 week) and job type filter (§7, §8)
- [ ] Hidden multilingual search words (§5)
- [ ] Starter sources: Adzuna, Bundesagentur für Arbeit, Reed, and a starter set of company career
      systems (§9)
- [ ] Duplicate detection with main-link priority (§10)
- [ ] Quality test set of 30–50 real job ads judged by the owner, and a tuned scoring prompt (§13)
- [ ] Scoring with 1–3 reasons per job (§11)
- [ ] Results screen with Save / Applied / Not interested (§12)
- [ ] Usage meter and caps (§13)
- [ ] **Done when:** the owner can run a real search on his Mac and get a ranked, deduplicated list
      with reasons.

## Phase 2: Smart location filter

- [ ] Location interpretation shown with the results, with an Edit option
- [ ] Reference datasets from HANDOVER §6 (places, boundaries, coastlines, UK sponsor register,
      German election results, country facts)
- [ ] **Done when:** all example sentences in HANDOVER §6 behave as described.

## Phase 3: Maximum coverage

- [ ] Source registry for every supported country (§9.0)
- [ ] All source types from §9.2–9.6: generic `JobPosting` reader, more career systems, employer
      directory
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
