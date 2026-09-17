# Jobcu

**Jobcu finds fresh job ads that fit you, from several job sites at once, and ranks them for you.**

You give Jobcu three things:

1. your CV
2. a cover letter that says who you are and what kind of job you want
3. a sentence about where you'd like to work, for example *"Munich or within 50 km"* or
   *"Germany, Ireland or the UK"*

When you press **Search**, Jobcu collects recent job ads, removes duplicates, leaves out jobs that
clearly don't fit, and shows a list ranked by how well each job fits you, with short reasons like
*"Strong PCB design match · Asks for 5+ years · German C1 required"*.

> 🧪 **This is an early test version for invited testers.** It works, but it's still being built,
> so some things are missing or may change. Your feedback helps a lot:
> [how to give feedback](#giving-feedback).

## Start here

Follow these three guides in order. Each one explains every click.

1. **[Install and start Jobcu](docs/guides/install-and-start.md)** on a Mac or on Windows
2. **[Get your keys](docs/guides/getting-your-keys.md)**: an AI key of your choice, plus free
   Adzuna and Reed keys
3. **[Your first search](docs/guides/first-search.md)**: set up Jobcu, search, and understand the
   results

Stuck? See **[Troubleshooting](docs/guides/troubleshooting.md)**.

## What you need

- **A Mac or a Windows computer** with an internet connection.
- **An API key from an AI provider of your choice.** An API key is like a password that lets
  Jobcu use an AI service on your account. Jobcu works with many providers and doesn't recommend
  any of them.
- **Free keys from Adzuna and Reed**, two job sites that let apps search their job ads.
- About 30 minutes for the first setup.

## Everything stays on your computer

- Jobcu runs on your own computer. There is no Jobcu website, account or cloud.
- Your CV, cover letter, searches, results and keys are saved only on your computer.
- Jobcu only connects to job sites and to the AI service you choose. It never sends anything to
  the people who made Jobcu.
- Jobcu never logs in to job sites, so your accounts on those sites are never at risk.

## What it can cost

- **Jobcu itself costs nothing.**
- **Your AI provider may charge for what Jobcu uses.** Some providers offer a free allowance,
  which can be enough for a few searches a day. Paid use depends on the provider and model you pick.
  In tests, one search used roughly 30,000–100,000 tokens (the pieces of text an AI reads and
  writes); broad searches use more. You can see the use of every search in **Search details**.
- **The Adzuna and Reed keys are free.**

## Where jobs come from (in this test version)

| Source | Countries | Notes |
|---|---|---|
| Adzuna | UK, Germany, Austria, Switzerland, Netherlands, Belgium, France, Italy, Spain, Poland | Free key. Limited free requests per day and month, so Jobcu uses them carefully. |
| Reed | UK | Free key. |
| Bundesagentur für Arbeit | Germany | Germany's public job agency. No key needed. |

More sources, and more countries such as Ireland, are planned.

## Giving feedback

The most useful things to tell us after a search:

- Do the **top results** look like jobs you'd apply for?
- Is any job **scored clearly too high or too low**? Which one, and why?
- In **Search details → "See the titles left out as clearly unrelated"**, was anything actually
  relevant to you?
- Was any step **confusing**, or did something **not work**? A screenshot helps (without keys or
  personal details in it).

Tell Utku directly, or, if you have a GitHub account with access, use the **Issues** tab on this
page → **New issue**.

## For people helping build Jobcu

- [How to help](CONTRIBUTING.md) and [instructions for AI coding assistants](AGENTS.md)
- [Progress](docs/PROGRESS.md), [decision log](docs/DECISIONS.md),
  [original concept](docs/HANDOVER.md)

---

© 2026 Utku Deniz Altiok. All rights reserved. See [LICENSE](LICENSE).
