import unittest

from utils.slo import percentile, evaluate_slo


class Pass15SLOGateTests(unittest.TestCase):
    def test_percentile_basic(self):
        vals = [10, 20, 30, 40, 50]
        self.assertAlmostEqual(percentile(vals, 50), 30.0)
        self.assertGreaterEqual(percentile(vals, 95), 40.0)

    def test_evaluate_slo_pass_and_fail(self):
        ok, summary_ok = evaluate_slo(
            latencies_ms=[100, 120, 140],
            errors=0,
            total=3,
            p95_budget_ms=200,
            max_error_rate=0.1,
        )
        self.assertTrue(ok)
        self.assertLessEqual(summary_ok["p95_ms"], 200)

        bad, summary_bad = evaluate_slo(
            latencies_ms=[100, 120, 1400],
            errors=1,
            total=3,
            p95_budget_ms=200,
            max_error_rate=0.1,
        )
        self.assertFalse(bad)
        self.assertGreater(summary_bad["error_rate"], 0.1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
