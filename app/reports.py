"""The four required outputs, all derived from matching.compute_all results.

None of these functions re-implement any part of the matching algorithm —
they only reshape MatrixResult objects into the reporting views described in
claude-code-build-brief-v2.md:
  1. Master lean training matrix (Profile x SOP)
  2. Comparison summary (per profile)
  3. Company-wide rollup, broken down by Primary_Department
  4. Gap report (Profile, SOP) list
"""

from __future__ import annotations

import csv
import io

from app.dataset import Dataset
from app.matching import MatrixResult


def _profile_label(r: MatrixResult) -> str:
    return f"{r.role_name} ({r.person_label})" if r.person_label else r.role_name


def master_matrix_rows(results: list[MatrixResult]) -> list[dict]:
    """One row per (Profile, SOP): Profile, SOP_ID, SOP_Title, Tier, Rationale."""
    rows = []
    for r in results:
        for a in r.assignments:
            rows.append(
                {
                    "Profile_ID": r.profile_id,
                    "Role_Name": r.role_name,
                    "Person_Label": r.person_label,
                    "Profile": _profile_label(r),
                    "SOP_ID": a.sop_id,
                    "SOP_Title": a.sop_title,
                    "Process_Area": a.process_area,
                    "Tier": a.tier,
                    "Rationale": a.rationale,
                }
            )
    return rows


def comparison_summary_rows(results: list[MatrixResult]) -> list[dict]:
    """One row per profile, matching expected-output-reference.csv's schema."""
    rows = []
    for r in results:
        rows.append(
            {
                "Profile_ID": r.profile_id,
                "Role": r.role_name,
                "Person": r.person_label,
                "Primary_Department": r.primary_department,
                "Conservative_SOPs": len(r.conservative_sop_ids),
                "Lean_MustKnow": len(r.must_know_sop_ids),
                "Lean_MustLocate": len(r.must_locate_sop_ids),
                "Gap_MissedByConservative": len(r.gap_sop_ids),
                "Conservative_Minutes": r.conservative_minutes,
                "Lean_Minutes": r.lean_minutes,
                "Minutes_Saved": r.minutes_saved,
                "Pct_Reduction": f"{r.pct_reduction:.1f}",
            }
        )
    return rows


def company_rollup_rows(results: list[MatrixResult]) -> list[dict]:
    """Aggregated totals plus a breakdown by Primary_Department.

    Returns one row per department, plus a final "TOTAL" row for the
    whole company.
    """
    by_dept: dict[str, dict[str, int]] = {}
    for r in results:
        bucket = by_dept.setdefault(
            r.primary_department,
            {
                "profile_count": 0,
                "conservative_sops": 0,
                "lean_must_know": 0,
                "lean_must_locate": 0,
                "gap_count": 0,
                "conservative_minutes": 0,
                "lean_minutes": 0,
                "minutes_saved": 0,
            },
        )
        bucket["profile_count"] += 1
        bucket["conservative_sops"] += len(r.conservative_sop_ids)
        bucket["lean_must_know"] += len(r.must_know_sop_ids)
        bucket["lean_must_locate"] += len(r.must_locate_sop_ids)
        bucket["gap_count"] += len(r.gap_sop_ids)
        bucket["conservative_minutes"] += r.conservative_minutes
        bucket["lean_minutes"] += r.lean_minutes
        bucket["minutes_saved"] += r.minutes_saved

    def _row(department: str, b: dict[str, int]) -> dict:
        pct = (
            round(b["minutes_saved"] / b["conservative_minutes"] * 100, 1)
            if b["conservative_minutes"]
            else 0.0
        )
        return {
            "Primary_Department": department,
            "Profile_Count": b["profile_count"],
            "Conservative_SOPs_Total": b["conservative_sops"],
            "Lean_MustKnow_Total": b["lean_must_know"],
            "Lean_MustLocate_Total": b["lean_must_locate"],
            "Gap_Count_Total": b["gap_count"],
            "Conservative_Minutes_Total": b["conservative_minutes"],
            "Lean_Minutes_Total": b["lean_minutes"],
            "Minutes_Saved_Total": b["minutes_saved"],
            "Pct_Reduction": f"{pct:.1f}",
        }

    rows = [_row(dept, b) for dept, b in by_dept.items()]

    company_totals: dict[str, int] = {
        "profile_count": 0,
        "conservative_sops": 0,
        "lean_must_know": 0,
        "lean_must_locate": 0,
        "gap_count": 0,
        "conservative_minutes": 0,
        "lean_minutes": 0,
        "minutes_saved": 0,
    }
    for b in by_dept.values():
        for key in company_totals:
            company_totals[key] += b[key]
    rows.append(_row("TOTAL", company_totals))
    return rows


def gap_report_rows(results: list[MatrixResult]) -> list[dict]:
    """(Profile, SOP) pairs where the SOP is a Must-Know gap."""
    rows = []
    for r in results:
        for a in r.assignments:
            if a.is_gap:
                rows.append(
                    {
                        "Profile_ID": r.profile_id,
                        "Role_Name": r.role_name,
                        "Person_Label": r.person_label,
                        "Profile": _profile_label(r),
                        "Primary_Department": r.primary_department,
                        "SOP_ID": a.sop_id,
                        "SOP_Title": a.sop_title,
                        "Rationale": a.rationale,
                    }
                )
    return rows


def rows_to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()
