"""Synthetic contract checks only; no physical simulation or algorithm benchmark."""
import math
import unittest
from src.bench_p1.preferences import (search_weights, evaluation_weights, exact_dominates,
    nondominated_indices, normalize, weighted_score, budget_indices, build_manifest, compositions)

class PreferenceTests(unittest.TestCase):
    def test_composition_count(self):
        self.assertEqual(len(list(compositions(4, 4))), 35)
        self.assertEqual(len(list(compositions(4, 5))), 70)
    def test_search_counts(self):
        self.assertEqual(len(search_weights(4)), 39)
        self.assertEqual(len(search_weights(5)), 76)
    def test_search_unit_sum(self):
        for d in (4, 5):
            for w in search_weights(d):
                self.assertAlmostEqual(sum(w), 1)
                self.assertGreaterEqual(min(w), 0)
    def test_search_has_equal_and_axes(self):
        for d in (4, 5):
            rows = search_weights(d)
            self.assertIn([1/d]*d, rows)
            for j in range(d):
                self.assertIn([float(i == j) for i in range(d)], rows)
    def test_evaluation_reproducible(self):
        self.assertEqual(evaluation_weights(5, 64, 3), evaluation_weights(5, 64, 3))
    def test_evaluation_positive(self):
        for w in evaluation_weights(5, 64, 3):
            self.assertGreater(min(w), 0)
            self.assertAlmostEqual(sum(w), 1)
    def test_evaluation_disjoint(self):
        for d in (4, 5):
            search = {tuple(w) for w in search_weights(d)}
            self.assertTrue(all(tuple(w) not in search for w in evaluation_weights(d, 64, 26092500+d)))
    def test_dimension_errors(self):
        with self.assertRaises(ValueError): exact_dominates([1], [1, 2])
        with self.assertRaises(ValueError): weighted_score([1], [.5, .5])
        with self.assertRaises(ValueError): normalize([1], [0, 0], [1])
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError): exact_dominates([math.nan], [0])
        with self.assertRaises(ValueError): normalize([math.inf], [0], [1])
    def test_bad_scales_and_weights(self):
        with self.assertRaises(ValueError): normalize([1], [0], [0])
        with self.assertRaises(ValueError): weighted_score([1, 2], [-1, 2])
        with self.assertRaises(ValueError): weighted_score([1, 2], [.2, .2])
    def test_no_clipping(self):
        self.assertEqual(normalize([-1, 3], [0, 0], [1, 1]), (-1, 3))
    def test_pareto_and_duplicate(self):
        self.assertEqual(nondominated_indices([[1, 3], [2, 2], [3, 3], [1, 3]]), [0, 1])
    def test_empty_archive(self):
        self.assertEqual(nondominated_indices([]), [])
        self.assertEqual(budget_indices([], {0: 1}), [])
    def test_split_sorties_not_total(self):
        a, b = [20, 8], [22, 5]
        self.assertFalse(exact_dominates(a, b))
        self.assertFalse(exact_dominates(b, a))
        self.assertTrue(exact_dominates([sum(b)], [sum(a)]))
    def test_positive_weight_optimum_is_nondominated_in_finite_set(self):
        rows = [[0, 3], [1, 1], [3, 0], [3, 3], [2, 2]]
        for w in evaluation_weights(2, 64, 8):
            best = min(range(len(rows)), key=lambda i: weighted_score(rows[i], w))
            self.assertIn(best, nondominated_indices(rows))
    def test_zero_weight_tie_can_be_dominated(self):
        self.assertEqual(weighted_score([0, 1], [1, 0]), weighted_score([0, 0], [1, 0]))
        self.assertTrue(exact_dominates([0, 0], [0, 1]))
    def test_nonconvex_frontier_and_budget(self):
        rows = [[0, 2], [1, 1.2], [2, 0]]
        self.assertEqual(nondominated_indices(rows), [0, 1, 2])
        for j in range(1001):
            scores = [weighted_score(r, [j/1000, 1-j/1000]) for r in rows]
            self.assertGreater(scores[1], min(scores))
        eligible = budget_indices(rows, {0: 1})
        self.assertEqual(min(eligible, key=lambda i: rows[i][1]), 1)
    def test_zero_anchor_does_not_scan(self):
        self.assertEqual({(1+e)*0 for e in [0, .01, .02, .05, .1]}, {0})
    def test_bad_budget(self):
        with self.assertRaises(ValueError): budget_indices([[1, 2]], {2: 1})
        with self.assertRaises(ValueError): budget_indices([[1, 2]], {0: math.inf})
    def test_scope_keeps_relay_coordinate(self):
        scopes = build_manifest()["sets"]
        self.assertEqual(len(scopes["Q2"]["objectives"]), 4)
        self.assertEqual(len(scopes["Q3"]["objectives"]), 5)
        self.assertEqual(scopes["Q3"]["objectives"][-2:], ["transport_sorties", "relay_sorties"])

if __name__ == "__main__": unittest.main(verbosity=2)
