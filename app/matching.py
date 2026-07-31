"""Core matching algorithm: role/profile -> per-SOP training tier.

Implements the algorithm from role-aware-training-spec.md /
claude-code-build-brief-v2.md exactly:

1. Conservative baseline: a SOP is assigned to a role if that role's
   Primary_Department (sourced from conservative_baseline.csv, never
   hardcoded) appears as a case-insensitive substring of the SOP's
   Broad_Applicability_Conservative field, OR that field contains
   "All Employees".
2. Lean Must-Know: SOPs governing any task in the profile's Task_IDs.
   tasks.csv's Governing_SOP_ID is the only source of truth for this —
   sops.csv's Key_Tasks_Governed is never consulted.
3. Lean Must-Locate: (Conservative-assigned) minus (Must-Know).
4. Not Applicable: everything else.
5. Gap: Must-Know SOPs that are NOT in the conservative-assigned set.

Rationale strings are template-generated from the data so the same input
always produces the identical output string — no LLM call is ever made here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.dataset import Dataset, Sop

DEFAULT_MUST_KNOW_MINUTES = 30
DEFAULT_MUST_LOCATE_MINUTES = 5
DEFAULT_CONSERVATIVE_MINUTES = 30

ALL_EMPLOYEES_MARKER = "all employees"

TIER_MUST_KNOW = "Must-Know"
TIER_MUST_LOCATE = "Must-Locate"
TIER_NOT_APPLICABLE = "Not Applicable"


@dataclass(frozen=True)
class SopAssignment:
    sop_id: str
    sop_title: str
    process_area: str
    tier: str
    rationale: str
    is_gap: bool


@dataclass(frozen=True)
class MatrixResult:
    profile_id: str
    role_name: str
    person_label: str
    primary_department: str
    assignments: tuple[SopAssignment, ...]
    conservative_sop_ids: frozenset[str]
    must_know_sop_ids: frozenset[str]
    must_locate_sop_ids: frozenset[str]
    not_applicable_sop_ids: frozenset[str]
    gap_sop_ids: frozenset[str]
    conservative_minutes: int
    lean_minutes: int
    minutes_saved: int
    pct_reduction: float


def _is_conservative_assigned(department: str, broad_applicability: str) -> bool:
    applicability_lower = broad_applicability.lower()
    if ALL_EMPLOYEES_MARKER in applicability_lower:
        return True
    return department.lower() in applicability_lower


def _rationale(
    sop: Sop,
    tier: str,
    department: str,
    matched_task_names: list[str],
    is_gap: bool,
) -> str:
    if tier == TIER_MUST_KNOW:
        tasks_text = "; ".join(matched_task_names)
        text = f"Role performs task(s) governed by this SOP: {tasks_text}."
        if is_gap:
            text += (
                f" This SOP falls outside the role's conservative department "
                f"assignment (Primary_Department: {department}; SOP applicability: "
                f"{sop.broad_applicability_conservative}) — flagged as a gap the "
                f"conservative department-based approach would have missed."
            )
        return text
    if tier == TIER_MUST_LOCATE:
        return (
            f"SOP applicability ('{sop.broad_applicability_conservative}') includes "
            f"role's Primary_Department ('{department}'), but role performs no task "
            f"this SOP governs. Role should know this SOP exists and where to locate "
            f"it, without requiring deep training."
        )
    return (
        f"SOP applicability ('{sop.broad_applicability_conservative}') does not "
        f"include role's Primary_Department ('{department}'), and role performs no "
        f"task this SOP governs."
    )


def compute_matrix(
    dataset: Dataset,
    profile_id: str,
    must_know_minutes: int = DEFAULT_MUST_KNOW_MINUTES,
    must_locate_minutes: int = DEFAULT_MUST_LOCATE_MINUTES,
    conservative_minutes_per_sop: int = DEFAULT_CONSERVATIVE_MINUTES,
) -> MatrixResult:
    """Compute the full training-tier matrix for one profile."""
    profile = dataset.profiles[profile_id]
    department = profile.primary_department

    # SOP_ID -> list of task names (in profile task order) that this
    # profile performs which are governed by that SOP.
    matched_tasks_by_sop: dict[str, list[str]] = {}
    for task_id in profile.task_ids:
        task = dataset.tasks[task_id]
        matched_tasks_by_sop.setdefault(task.governing_sop_id, []).append(task.task_name)

    must_know_sop_ids = frozenset(matched_tasks_by_sop.keys())

    conservative_sop_ids = frozenset(
        sop.sop_id
        for sop in dataset.sops.values()
        if _is_conservative_assigned(department, sop.broad_applicability_conservative)
    )

    must_locate_sop_ids = conservative_sop_ids - must_know_sop_ids
    gap_sop_ids = must_know_sop_ids - conservative_sop_ids
    not_applicable_sop_ids = (
        frozenset(dataset.sops.keys()) - conservative_sop_ids - must_know_sop_ids
    )

    assignments: list[SopAssignment] = []
    for sop_id, sop in dataset.sops.items():
        is_gap = sop_id in gap_sop_ids
        if sop_id in must_know_sop_ids:
            tier = TIER_MUST_KNOW
        elif sop_id in must_locate_sop_ids:
            tier = TIER_MUST_LOCATE
        else:
            tier = TIER_NOT_APPLICABLE
        rationale = _rationale(
            sop, tier, department, matched_tasks_by_sop.get(sop_id, []), is_gap
        )
        assignments.append(
            SopAssignment(
                sop_id=sop_id,
                sop_title=sop.title,
                process_area=sop.process_area,
                tier=tier,
                rationale=rationale,
                is_gap=is_gap,
            )
        )

    conservative_minutes = len(conservative_sop_ids) * conservative_minutes_per_sop
    lean_minutes = (
        len(must_know_sop_ids) * must_know_minutes
        + len(must_locate_sop_ids) * must_locate_minutes
    )
    minutes_saved = conservative_minutes - lean_minutes
    pct_reduction = (
        round(minutes_saved / conservative_minutes * 100, 1)
        if conservative_minutes
        else 0.0
    )

    return MatrixResult(
        profile_id=profile.profile_id,
        role_name=profile.role_name,
        person_label=profile.person_label,
        primary_department=department,
        assignments=tuple(assignments),
        conservative_sop_ids=conservative_sop_ids,
        must_know_sop_ids=must_know_sop_ids,
        must_locate_sop_ids=must_locate_sop_ids,
        not_applicable_sop_ids=not_applicable_sop_ids,
        gap_sop_ids=gap_sop_ids,
        conservative_minutes=conservative_minutes,
        lean_minutes=lean_minutes,
        minutes_saved=minutes_saved,
        pct_reduction=pct_reduction,
    )


def compute_all(dataset: Dataset, **kwargs) -> list[MatrixResult]:
    """compute_matrix for every profile, in profiles.csv order."""
    return [compute_matrix(dataset, pid, **kwargs) for pid in dataset.profile_order()]
