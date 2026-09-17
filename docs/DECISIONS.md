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
