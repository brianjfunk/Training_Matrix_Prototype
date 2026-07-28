# Project: Role-Aware Training Matrix (v1 prototype)

Full spec: see `claude-code-build-brief-v2.md` and `role-aware-training-spec.md`. Read both before writing code.

## Hard constraints (do not violate these under any circumstance, including refactors)

1. **`Primary_Department` is data, not code.** It must be read from each company's `conservative_baseline.csv` at load time. Never hardcode a role-to-department mapping table anywhere in the application.
2. **Rationale text is template-generated, never an LLM call.** It must be exact and reproducible — the same input always produces the identical rationale string. Do not call the Anthropic API or any LLM to generate rationale text.
3. **`tasks.csv`'s `Governing_SOP_ID` is the only source of truth for task-to-SOP mapping.** The `Key_Tasks_Governed` column in `sops.csv` is vestigial raw material used to build `tasks.csv` originally — ignore it entirely. Do not attempt to reconcile or re-derive anything from it.
4. **No company-specific logic anywhere in the app.** Nothing in the codebase should reference `validated-vascular-access-co`, its specific role names, or its specific department names. If you find yourself writing a conditional that only makes sense for one company's data, that's a bug.
5. **Out of scope, do not build:** multi-tenant auth/billing, live QMS integration, automatic SOP-text-to-task NLP inference, AI-detected just-in-time training triggers, PDF export.

## Success criteria (both must hold)
1. Running the app against `companies/validated-vascular-access-co/` and computing all 16 profiles must match `companies/validated-vascular-access-co/expected-output-reference.csv` exactly.
2. The same code path must work correctly on any other conforming dataset without modification.

## Required file: tests/validate_against_reference.py
The Stop hook (`.claude/settings.json`) depends on this script existing and being runnable. Create it early: it should load `companies/validated-vascular-access-co/`, run the app's matching logic for all 16 profiles, compare against `expected-output-reference.csv`, and exit 0 if everything matches or exit 1 otherwise. Without this file, the Stop hook will block indefinitely.

## Workflow
1. Start by using the `planner` subagent to turn the brief into a task list.
2. Implement in the main thread.
3. Before declaring the build done, the `qa-verifier` subagent must run and both its checks must pass. The Stop hook enforces this — see `.claude/settings.json`.
