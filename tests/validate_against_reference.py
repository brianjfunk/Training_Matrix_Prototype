#!/usr/bin/env python3
"""Validate compute_matrix output against the built-in reference dataset.

Loads companies/validated-vascular-access-co/, runs the matching logic for
all 16 profiles, and compares the resulting comparison-summary numbers
against expected-output-reference.csv column-for-column. Exits 0 if every
row matches exactly, 1 otherwise (with a diff of the first mismatches).

This script is required by CLAUDE.md's Stop hook workflow and must keep
working standalone: `python3 tests/validate_against_reference.py`.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.dataset import load_dataset
from app.matching import compute_all

DEFAULT_COMPANY_DIR = REPO_ROOT / "companies" / "validated-vascular-access-co"
REFERENCE_CSV = DEFAULT_COMPANY_DIR / "expected-output-reference.csv"


def build_actual_rows(company_dir: Path) -> list[dict[str, str]]:
    dataset = load_dataset(company_dir)
    results = compute_all(dataset)
    rows = []
    for r in results:
        rows.append(
            {
                "Role": r.role_name,
                "Person": r.person_label,
                "Conservative_SOPs": str(len(r.conservative_sop_ids)),
                "Lean_MustKnow": str(len(r.must_know_sop_ids)),
                "Lean_MustLocate": str(len(r.must_locate_sop_ids)),
                "Gap_MissedByConservative": str(len(r.gap_sop_ids)),
                "Conservative_Minutes": str(r.conservative_minutes),
                "Lean_Minutes": str(r.lean_minutes),
                "Minutes_Saved": str(r.minutes_saved),
                "Pct_Reduction": f"{r.pct_reduction:.1f}",
            }
        )
    return rows


def load_reference_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> int:
    if not REFERENCE_CSV.exists():
        print(f"FAIL: reference file not found: {REFERENCE_CSV}")
        return 1

    expected_rows = load_reference_rows(REFERENCE_CSV)
    actual_rows = build_actual_rows(DEFAULT_COMPANY_DIR)

    if len(actual_rows) != len(expected_rows):
        print(
            f"FAIL: expected {len(expected_rows)} profile rows, "
            f"got {len(actual_rows)}"
        )
        return 1

    columns = list(expected_rows[0].keys())
    mismatches = []
    for i, (expected, actual) in enumerate(zip(expected_rows, actual_rows)):
        for col in columns:
            exp_val = (expected.get(col) or "").strip()
            act_val = (actual.get(col) or "").strip()
            if exp_val != act_val:
                mismatches.append(
                    f"row {i} ({expected.get('Role')} / {expected.get('Person')}) "
                    f"column {col!r}: expected {exp_val!r}, got {act_val!r}"
                )

    if mismatches:
        print(f"FAIL: {len(mismatches)} mismatch(es) against {REFERENCE_CSV.name}:")
        for m in mismatches[:30]:
            print(f"  - {m}")
        return 1

    print(f"PASS: all {len(expected_rows)} profiles match {REFERENCE_CSV.name} exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
