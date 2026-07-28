# Role-Aware Training Matrix — V1 Product Spec

## One-line description
Given a company's SOP library and each role's actual scope of work, generate a defensible per-role training matrix that splits SOPs into **Must-Know** (train deeply, verify comprehension) and **Must-Locate** (aware it exists, know where to find it) — with an audit-ready rationale for every exclusion.

## Problem this solves
Medical device companies over-assign SOP training because job descriptions are broad and defensively written. Employees spend hours reviewing/acknowledging documents irrelevant to their actual work, often just checking a box without real review. This wastes measurable hours per employee per year and creates a false sense of compliance (box-checking is not competence) — while a poorly-scoped matrix is itself an audit risk in the other direction (missing required training).

## Core objects / data model

**SOP**
- `id`, `title`, `revision`, `effective_date`
- `scope_text` — the SOP's own stated purpose/scope (from document header)
- `applicable_departments` — as currently defined in the SOP's doc-control metadata (often overly broad — this is the input we're correcting)
- `governed_tasks` — list of discrete QMS actions this SOP controls (see Task below)

**Task**
- `id`, `name` (e.g., "initiates CAPA," "signs DVR," "releases controlled inventory," "performs process validation run," "certifies cleanroom")
- `related_sop_ids` — which SOPs govern this task
- These should be a finite, reusable taxonomy — not free text — so profiles stay comparable across roles and companies.

**Role Profile**
- `id`, `role_name`, `department`
- `tasks_performed` — subset of the Task taxonomy this role actually does (QA-approved, not self-reported job description text)
- `people_count` — for the savings calculation

**Person** (optional in v1 — can operate at role level only for the demo)
- `id`, `assigned_role_id`, `hire_date`

**Training Matrix Entry** (the output)
- `role_id`, `sop_id`, `tier` (Must-Know / Must-Locate / Not Applicable)
- `rationale` — auto-generated explanation ("Role performs Task X, which SOP Y governs" / "Role does not perform any task governed by this SOP")
- `requires_qa_approval` — flag, always true; nothing ships to a real training matrix without a human QA sign-off in v1

## Core algorithm (v1, deliberately simple)
1. For each SOP, resolve its `governed_tasks` (manual/curated mapping for the demo dataset — this is domain work, not something to auto-infer from SOP text in v1).
2. For each Role Profile, compare `tasks_performed` against each SOP's `governed_tasks`.
   - Overlap exists → **Must-Know**
   - No overlap, but SOP is in the role's declared department → **Must-Locate**
   - No overlap and outside department → **Not Applicable**
3. Generate rationale text per entry (template-based, not LLM-generated for v1 — needs to be exact and auditable, not paraphrased).
4. Aggregate into a per-role and per-company summary: SOPs eliminated from deep training, estimated hours saved (using a configurable "avg minutes per SOP review" input).

**Explicitly not in v1:** any ML/NLP inference of task-to-SOP mapping from raw SOP text. That mapping should be manually curated for the demo dataset so the mechanism's *output* is trustworthy and demoable — auto-extraction is a real feature but a separate, harder problem that would undermine confidence in the first prototype if it's wrong.

## Inputs needed for the demo
- A synthetic SOP set (10–20 SOPs) built from public material: FDA 21 CFR 820 guidance language, published ISO 13485 template structures, and SOP excerpts quoted in public FDA warning letters. Paraphrased into original synthetic documents — not copied from any real company.
- 4–6 role profiles spanning a realistic org slice (e.g., Phase 0 Engineer, Manufacturing Engineer, QA Specialist, Buyer/Planner, Test Technician) with manually defined task lists reflecting real scope-of-work patterns (this is where your 10 years of domain knowledge does the actual work).
- A configurable "hours saved" assumption (e.g., 30 min per unnecessary SOP review) to produce the dollar/hour output.

## V1 outputs (what "finished prototype" means)
1. A training matrix table: role x SOP x tier x rationale.
2. A summary report: total SOPs per role before vs. after, hours saved estimate, company-wide rollup.
3. Exportable as CSV/PDF — needs to look like something you could hand to a QA director, not just a database dump.

## Explicitly out of scope for v1
- Multi-tenant accounts, auth, billing
- LMS delivery / actual training content or video generation
- Any integration with a real company's live QMS/PLM system
- Automatic SOP-text-to-task inference (NLP)
- SOC 2 or any compliance certification (only relevant once real customer data is involved)

## Success criteria
You can hand this to a former colleague or a design-partner prospect and, within one 30-minute session, they can see their own (synthetic-analog) role produce a plausible, defensible Must-Know/Must-Locate split with a rationale they'd trust in front of an auditor.

## Suggested build approach for Claude Code
- Backend: simple, e.g. Python + SQLite (or even just structured JSON/CSV files for v1 — no need for a real database yet).
- Minimal web UI (single page: upload/select role, view matrix + rationale + summary numbers) — good enough for a live demo screen-share, not production-grade.
- Keep the task taxonomy and SOP-to-task mapping in an editable config file (CSV/YAML) so you can hand-tune the demo dataset without touching code.
