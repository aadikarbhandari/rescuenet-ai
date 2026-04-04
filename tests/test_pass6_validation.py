import unittest
from unittest.mock import patch

from agents.triage import TriageAgent
from agents.coordinator import CoordinatorAgent
from state.fleet_state import FleetState
from utils.reliability import CircuitBreaker
from api.server import update_state, get_ops_metrics


class Pass6ValidationTests(unittest.TestCase):
    def test_triage_parser_normalizes_aliases_and_fenced_json(self):
        agent = TriageAgent()
        response = """```json
        {
          \"triage_score\": 91,
          \"severity\": \"urgent\",
          \"reason\": \"Needs immediate evacuation\",
          \"action\": \"evacuate to medical facility\"
        }
        ```"""
        parsed = agent._parse_llm_response(response)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["score"], 91)
        self.assertEqual(parsed["priority"], "critical")
        self.assertEqual(parsed["recommended_action"], "extract")

    def test_circuit_breaker_opens_and_recovers(self):
        breaker = CircuitBreaker(failure_threshold=2, reset_timeout_seconds=1)
        self.assertTrue(breaker.allow_request())
        breaker.record_failure()
        self.assertTrue(breaker.allow_request())
        breaker.record_failure()
        self.assertFalse(breaker.allow_request())

        # fast-forward time by patching opened_at in-place
        with patch("utils.reliability.datetime") as mock_dt:
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            mock_dt.utcnow.return_value = now + timedelta(seconds=2)
            self.assertTrue(breaker.allow_request())

    def test_rule_based_dispatch_assigns_highest_priority_first(self):
        fleet = FleetState(drone_names=["drone_1", "drone_2"])
        coordinator = CoordinatorAgent(fleet)

        victims = [
            {"victim_id": "victim_low", "score": 40, "x": 2, "y": 0, "z": 0},
            {"victim_id": "victim_high", "score": 95, "x": 1, "y": 0, "z": 0},
        ]
        assignments = coordinator._rule_based_dispatch(fleet.get_available_drones(), victims)

        self.assertEqual(len(assignments), 2)
        self.assertEqual(assignments[0]["victim_id"], "victim_high")

    def test_ops_metrics_endpoint_returns_latest_snapshot(self):
        update_state(
            {
                "ops_metrics": {
                    "ticks": 3,
                    "llm_triage_success": 2,
                    "llm_triage_fallback": 1,
                    "avg_tick_ms": 123.4,
                }
            }
        )
        metrics = get_ops_metrics()
        self.assertEqual(metrics["ticks"], 3)
        self.assertEqual(metrics["llm_triage_success"], 2)
        self.assertAlmostEqual(metrics["avg_tick_ms"], 123.4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
