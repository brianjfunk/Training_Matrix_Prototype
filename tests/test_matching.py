#!/usr/bin/env python3
"""Unit tests for the matching algorithm against the synthetic portability
fixture (companies/synthetic-portability-check/), covering edge cases the
16-profile reference dataset doesn't specifically isolate: case-insensitive
substring matching, the "All Employees" marker, and gap detection.

Run with: python3 tests/test_matching.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.dataset import load_dataset
from app.matching import compute_matrix

FIXTURE_DIR = REPO_ROOT / "companies" / "synthetic-portability-check"


class MatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = load_dataset(FIXTURE_DIR)

    def test_all_employees_marker_is_conservative_for_every_department(self):
        for profile_id in self.dataset.profile_order():
            result = compute_matrix(self.dataset, profile_id)
            self.assertIn("SOP-A1", result.conservative_sop_ids)

    def test_department_substring_is_case_insensitive(self):
        result = compute_matrix(self.dataset, "P-2")  # Engineering
        self.assertIn("SOP-A5", result.conservative_sop_ids)  # applicability "Engineering"

    def test_must_know_from_tasks_only(self):
        result = compute_matrix(self.dataset, "P-1")  # Warehouse Associate: TK-01, TK-02
        self.assertEqual(result.must_know_sop_ids, frozenset({"SOP-A1", "SOP-A2"}))

    def test_must_locate_is_conservative_minus_must_know(self):
        result = compute_matrix(self.dataset, "P-2")  # Engineering
        self.assertEqual(result.must_locate_sop_ids, frozenset({"SOP-A1"}))
        self.assertNotIn("SOP-A5", result.must_locate_sop_ids)

    def test_gap_flags_must_know_outside_conservative_set(self):
        result = compute_matrix(self.dataset, "P-3")  # Support Agent, also does TK-04 (Procurement)
        self.assertEqual(result.gap_sop_ids, frozenset({"SOP-A4"}))
        self.assertIn("SOP-A4", result.must_know_sop_ids)
        self.assertNotIn("SOP-A4", result.conservative_sop_ids)

    def test_not_applicable_excludes_conservative_and_must_know(self):
        result = compute_matrix(self.dataset, "P-1")
        self.assertEqual(
            result.not_applicable_sop_ids,
            frozenset(self.dataset.sops.keys())
            - result.conservative_sop_ids
            - result.must_know_sop_ids,
        )

    def test_minutes_can_go_negative_when_gaps_outweigh_savings(self):
        result = compute_matrix(self.dataset, "P-3")
        self.assertEqual(result.conservative_minutes, 60)
        self.assertEqual(result.lean_minutes, 65)
        self.assertEqual(result.minutes_saved, -5)

    def test_overtraining_and_gap_minutes_reconcile_to_net_minutes_saved(self):
        # P-3 (Support Agent) has a gap (SOP-A4) that costs more than the
        # Must-Locate downgrade (SOP-A1) saves, so the net is negative even
        # though both components are individually well-defined and >= 0.
        result = compute_matrix(self.dataset, "P-3")
        self.assertEqual(result.overtraining_minutes_saved, 25)  # SOP-A1: 30 - 5
        self.assertEqual(result.gap_training_minutes_required, 30)  # SOP-A4: 1 gap * 30
        self.assertEqual(
            result.overtraining_minutes_saved - result.gap_training_minutes_required,
            result.minutes_saved,
        )

    def test_overtraining_and_gap_minutes_reconcile_for_every_profile(self):
        # The identity must hold everywhere, not just the one negative-net
        # fixture profile, and regardless of custom time assumptions.
        for profile_id in self.dataset.profile_order():
            result = compute_matrix(
                self.dataset,
                profile_id,
                must_know_minutes=45,
                must_locate_minutes=10,
                conservative_minutes_per_sop=20,
            )
            self.assertEqual(
                result.overtraining_minutes_saved - result.gap_training_minutes_required,
                result.minutes_saved,
            )

    def test_custom_time_assumptions_change_the_result(self):
        default_result = compute_matrix(self.dataset, "P-2")
        custom_result = compute_matrix(
            self.dataset,
            "P-2",
            must_know_minutes=100,
            must_locate_minutes=1,
            conservative_minutes_per_sop=1,
        )
        self.assertNotEqual(default_result.lean_minutes, custom_result.lean_minutes)
        self.assertEqual(custom_result.conservative_minutes, 2)  # 2 conservative SOPs * 1
        self.assertEqual(custom_result.lean_minutes, 100 + 1)  # 1 Must-Know*100 + 1 Must-Locate*1


class ComparisonSummaryDisplayTests(unittest.TestCase):
    """Covers the display/reporting layer (app/reports.py), not just the
    underlying compute_matrix math: does the comparison summary actually
    surface the two separate time figures instead of only the net?
    """

    @classmethod
    def setUpClass(cls):
        cls.dataset = load_dataset(FIXTURE_DIR)

    def test_comparison_summary_exposes_both_components_and_the_net(self):
        from app.matching import compute_all
        from app.reports import comparison_summary_rows

        results = compute_all(self.dataset)
        rows = {r["Role"]: r for r in comparison_summary_rows(results)}
        support_agent_row = rows["Support Agent"]

        self.assertEqual(support_agent_row["Time_Saved_Reduced_Overtraining"], 25)
        self.assertEqual(support_agent_row["Time_Required_Gap_Training"], 30)
        self.assertEqual(support_agent_row["Minutes_Saved"], -5)
        # The net figure must still be present and correct (reference-CSV
        # compatibility) even though it's negative and no longer the only
        # number shown.
        self.assertEqual(
            support_agent_row["Time_Saved_Reduced_Overtraining"]
            - support_agent_row["Time_Required_Gap_Training"],
            support_agent_row["Minutes_Saved"],
        )

    def test_company_rollup_aggregates_both_components(self):
        from app.matching import compute_all
        from app.reports import company_rollup_rows

        results = compute_all(self.dataset)
        rows = {r["Primary_Department"]: r for r in company_rollup_rows(results)}
        total_row = rows["TOTAL"]

        expected_overtraining_total = sum(
            r.overtraining_minutes_saved for r in compute_all(self.dataset)
        )
        expected_gap_total = sum(
            r.gap_training_minutes_required for r in compute_all(self.dataset)
        )
        self.assertEqual(
            total_row["Time_Saved_Reduced_Overtraining_Total"], expected_overtraining_total
        )
        self.assertEqual(
            total_row["Time_Required_Gap_Training_Total"], expected_gap_total
        )
        self.assertEqual(
            total_row["Time_Saved_Reduced_Overtraining_Total"]
            - total_row["Time_Required_Gap_Training_Total"],
            total_row["Minutes_Saved_Total"],
        )


if __name__ == "__main__":
    unittest.main()
