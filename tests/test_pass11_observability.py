import unittest

from utils.observability import OpsMetrics


class Pass11ObservabilityTests(unittest.TestCase):
    def test_ops_metrics_percentiles_and_max(self):
        m = OpsMetrics()
        for tick_ms in [10.0, 20.0, 30.0, 40.0, 50.0]:
            m.record_tick(tick_ms)

        data = m.to_dict()
        self.assertEqual(data["ticks"], 5)
        self.assertAlmostEqual(data["avg_tick_ms"], 30.0, places=2)
        self.assertAlmostEqual(data["p50_tick_ms"], 30.0, places=2)
        self.assertGreaterEqual(data["p95_tick_ms"], 40.0)
        self.assertEqual(data["max_tick_ms"], 50.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
