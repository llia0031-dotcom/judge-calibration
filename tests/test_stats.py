"""Offline checks of the agreement statistics against values computed independently from the formulas."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from judgecal import stats  # noqa: E402


def two_by_two(a, b, c, d):
    """Rater lists from a 2x2 table: a both yes, b first yes / second no, c first no / second yes, d both no."""
    r1 = ["y"] * a + ["y"] * b + ["n"] * c + ["n"] * d
    r2 = ["y"] * a + ["n"] * b + ["y"] * c + ["n"] * d
    return r1, r2


class Stats(unittest.TestCase):
    def test_wilson_matches_closed_form(self):
        k, n, z = 45, 50, 1.959963984540054
        p = k / n
        centre = (p + z * z / (2 * n)) / (1 + z * z / n)
        half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        lo, hi = stats.wilson(k, n)
        self.assertAlmostEqual(lo, centre - half, places=9)
        self.assertAlmostEqual(hi, centre + half, places=9)

    def test_wilson_edges(self):
        lo, hi = stats.wilson(0, 20)
        self.assertEqual(lo, 0.0)
        self.assertGreater(hi, 0.1)
        lo, hi = stats.wilson(20, 20)
        self.assertAlmostEqual(hi, 1.0, places=12)
        self.assertLess(lo, 0.9)
        self.assertTrue(math.isnan(stats.wilson(0, 0)[0]))

    def test_kappa_and_ac1_balanced_table(self):
        r1, r2 = two_by_two(40, 9, 6, 45)
        # pa = 0.85; kappa: pe = .49*.46 + .51*.54 = .5008; AC1: pe = 2 * .475 * .525 = .49875
        self.assertAlmostEqual(stats.cohen_kappa(r1, r2), (0.85 - 0.5008) / (1 - 0.5008), places=9)
        self.assertAlmostEqual(stats.gwet_ac1(r1, r2), (0.85 - 0.49875) / (1 - 0.49875), places=9)

    def test_kappa_paradox(self):
        """90% agreement on a lopsided table: kappa goes slightly negative, AC1 stays high."""
        r1, r2 = two_by_two(90, 5, 5, 0)
        self.assertAlmostEqual(stats.cohen_kappa(r1, r2), (0.90 - 0.905) / (1 - 0.905), places=9)
        self.assertAlmostEqual(stats.gwet_ac1(r1, r2), (0.90 - 0.095) / (1 - 0.095), places=9)

    def test_kappa_undefined_when_one_label(self):
        self.assertTrue(math.isnan(stats.cohen_kappa(["y"] * 5, ["y"] * 5)))
        self.assertTrue(math.isnan(stats.gwet_ac1(["y"] * 5, ["y"] * 5)))

    def test_weighted_kappa_perfect_and_shifted(self):
        a = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
        self.assertAlmostEqual(stats.cohen_kappa(a, a, weights="quadratic"), 1.0)
        b = [2, 3, 4, 5, 5, 1, 2, 3, 4, 4]
        k = stats.cohen_kappa(a, b, weights="quadratic")
        self.assertTrue(0.5 < k < 1.0)

    def test_fleiss_perfect_and_mixed(self):
        self.assertAlmostEqual(stats.fleiss([["y"] * 3, ["n"] * 3, ["y"] * 3, ["n"] * 3]), 1.0)
        mixed = stats.fleiss([["y", "y", "n"], ["n", "n", "y"], ["y", "n", "y"], ["n", "y", "n"]])
        self.assertLess(mixed, 0.1)

    def test_krippendorff_perfect(self):
        self.assertAlmostEqual(stats.kripp_alpha([[1, 2, 3, 4], [1, 2, 3, 4]]), 1.0)

    def test_mcnemar(self):
        self.assertEqual(stats.mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(stats.mcnemar_exact(0, 6), 2 * 0.5 ** 6, places=9)

    def test_bootstrap_is_reproducible_and_brackets_the_mean(self):
        import numpy as np

        x = np.array([0] * 30 + [1] * 70)
        f = lambda idx: float(x[idx].mean())  # noqa: E731
        a, b = stats.bootstrap(f, len(x)), stats.bootstrap(f, len(x))
        self.assertEqual(a, b)
        self.assertTrue(a[0] < 0.7 < a[1])
        self.assertTrue(0.55 < a[0] and a[1] < 0.85)

    def test_agreement_block_counts(self):
        truth = ["fail"] * 10 + ["pass"] * 10
        judged = ["fail"] * 8 + ["pass"] * 2 + ["pass"] * 9 + ["fail"]
        blk = stats.agreement_block(truth, judged, positive="fail")
        self.assertEqual(blk["agreement"]["k"], 17)
        self.assertEqual((blk["recall"]["k"], blk["recall"]["n"]), (8, 10))
        self.assertEqual((blk["false_positive"]["k"], blk["false_positive"]["n"]), (1, 10))


if __name__ == "__main__":
    unittest.main()
