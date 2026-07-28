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


if __name__ == "__main__":
    unittest.main()
