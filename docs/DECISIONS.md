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
| The repository starts on the owner's personal GitHub account. **Before friends are invited (Phase 4), it moves to a free GitHub "organization"** (a shared space on GitHub) | On a personal account, anyone given access can also change the code. Only an organization can give friends download-only access. Moving keeps all history and dates. |
| The concept document is kept unchanged at `docs/HANDOVER.md` from the first commit | The concept requires this as a dated record of the owner's work. |
