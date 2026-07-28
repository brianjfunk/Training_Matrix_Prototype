# Role-Aware Training Matrix — Claude Code Build Brief (v2)

## What changed from v1
v1 hardcoded one company's data and its department-mapping logic directly into the app. That was wrong for the actual goal: this needs to be a general-purpose tool that ingests **any** conforming dataset — a real customer's collected QMS data, or a new synthetic company — not a demo wired to one fixed company. This version defines the input contract explicitly and treats our validated company as the built-in default fixture, not the only dataset the app can ever run.

## The input contract (the app's actual "API")
Any company dataset — real or synthetic — must be supplied as five files matching this schema. The app's matching logic operates only on these fields; it should never assume anything about a specific company's identity.

**`sops.csv`** — one row per controlled document
`SOP_ID, Title, Process_Area, Summary, Broad_Applicability_Conservative, Key_Tasks_Governed`

**`tasks.csv`** — normalized task taxonomy
`Task_ID, Task_Name, Process_Area, Governing_SOP_ID`

**`profiles.csv`** — one row per role or per-person variant
`Profile_ID, Role_Name, Person_Label, Primary_Department, Task_IDs` (Task_IDs is a semicolon-delimited list)

**`conservative_baseline.csv`** — the "what department would this role currently be filed under" data
`Role_Name, Primary_Department`
For a real customer, this is collected by directly asking their training/quality coordinator, not researched externally. For a synthetic company, it can be derived from real job-posting research as we did for the validated test case. The app doesn't care about provenance — only that the field is populated.

**`projects.csv`** (optional) — contextual only, does not feed the matching logic
`Project_ID, Project_Name, Status, Description`

**Critical architecture rule: `Primary_Department` is data, not code.** Do not hardcode any role-to-department mapping table inside the application. It must be read from `conservative_baseline.csv` at load time. This is the single most important correction from v1 — a hardcoded mapping breaks the moment a second company with different role names is loaded.

## Matching logic (unchanged in substance from v1 — still validated, still implement exactly)

1. **Conservative baseline**: A SOP is assigned to a role if that role's `Primary_Department` (from `conservative_baseline.csv`) appears as a case-insensitive substring in the SOP's `Broad_Applicability_Conservative` field, OR that field contains "All Employees".
2. **Lean Must-Know**: SOPs governing any task in the profile's `Task_IDs`.
3. **Lean Must-Locate**: (Conservative-assigned) minus (Must-Know).
4. **Not Applicable**: everything else.
5. **Gap flag**: Must-Know SOPs NOT in the conservative-assigned set — surface explicitly, this is a distinct product claim (catches blind spots, not just waste).

## Required outputs (all exportable to CSV)
1. **Master lean training matrix** — one row per (Profile × SOP): Profile, SOP_ID, SOP_Title, Tier, Rationale (template-generated, not LLM-generated — see reasoning in the original product spec doc).
2. **Comparison summary** — one row per profile: Conservative_Count, Lean_MustKnow, Lean_MustLocate, Gap_Count, Hours_Saved, Pct_Reduction (using editable time-per-review assumptions, defaults 30 min Must-Know / 5 min Must-Locate).
3. **Company-wide rollup** — aggregated totals, with a breakdown by department/function so it's visible where the tool helps most vs. least.
4. **Gap report** — explicit (Profile, SOP) list of flagged gaps.

## Company dataset loading
- The app ships with **one built-in default dataset**: the validated company we already built (114 SOPs, 185 tasks, 16 profiles). This serves as both the working demo and a regression fixture — the app's output against this dataset must continue to match `comparison-results-v2-primary-dept.csv` exactly after any change.
- Additional companies are loaded via a simple **import mechanism** (file upload of the five CSVs, or a folder drop — whichever is simpler to implement well) — not pre-baked into the app's code or shipped as hardcoded options. Loading a new company should require zero code changes.
- No accounts, no multi-tenancy, no persistence layer beyond "which dataset is currently loaded" — this is a single-user tool for now, not a SaaS product. Switching datasets can be a simple "load a different folder/set of files" action.

## Explicitly OUT of scope for v1 — do not build
- Multi-tenant accounts, auth, billing, or SOC 2 / compliance certification of the tool itself.
- Any live integration with a real company's QMS/PLM system — import is file-based only.
- Automatic SOP-text-to-task NLP inference — `tasks.csv` is always a curated input, never derived by the app.
- AI-detected just-in-time training triggers (inferring training need from email/calendar/browsing activity). Real v2+ direction; deliberately excluded now because validating a static task-to-SOP mapping to an auditor is tractable, validating an AI's behavioral inference is a much harder and different problem, and conflating the two undermines this build's credibility as a first demo.
- PDF export — CSV is sufficient for v1.

## Documented future direction (preserve the hook, don't build)
Just-in-time training: promote a person from Must-Locate to Must-Know when assigned a new task, timestamped. Compatible with the current two-tier model without a schema redesign.

## Success criteria
1. Loading the built-in default dataset and reading off computed numbers for all 16 profiles must reproduce `comparison-results-v2-primary-dept.csv` exactly.
2. Loading a second, different conforming dataset (we will supply one to test with) must produce correct output using the same code path — no company-specific logic anywhere in the app.
3. Any mismatch in (1) is a bug to fix; any special-casing found in service of (2) is also a bug to fix.

## Recommended Claude Code session setup
- **Permissions**: set an allowlist in `.claude/settings.json` covering file edits within the project directory and test/build/lint commands, with explicit deny rules for destructive shell operations (`rm -rf`, `git push`, arbitrary network calls). Avoids constant interruption without going fully unsupervised.
- **Test-on-edit hook**: a `PostToolUse` hook that reruns the validation check (output vs. `comparison-results-v2-primary-dept.csv`) after every file edit, so "done" means the numbers are actually still correct, not just a plausible-looking diff.
- **Visual verification**: if using Claude Code's desktop app, use the built-in browser pane (`Cmd+Shift+B` / `Ctrl+Shift+B`) to navigate to the running local app and click through all 16 profiles as a final check — this is now native, no separate browser-automation MCP server needed. Explicitly ask for this as a last step before considering the build done; it won't happen automatically just because the brief mentions it.

## Suggested technical approach
- Backend: Python, loading the currently-active dataset's five CSVs into memory. No real database needed at this data size.
- Frontend: single-page, kept simple — clarity for a live demo matters more than polish at this stage.
- Matching logic as a separately testable module (e.g. `compute_matrix(dataset, profile_id)`) so it can be unit-tested against the reference CSV directly, and reused identically regardless of which dataset is loaded.
