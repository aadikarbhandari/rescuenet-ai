import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.server import app, update_state
from utils import reliability
from utils.reliability import CircuitBreaker, RetryPolicy, resilient_post


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class Pass8IntegrationTests(unittest.TestCase):
    def setUp(self):
        reliability._BREAKERS.clear()

    def test_resilient_post_retries_then_succeeds(self):
        policy = RetryPolicy(max_attempts=2, timeout_seconds=1, base_delay_seconds=0, max_delay_seconds=0)
        responses = [_FakeResponse(500), _FakeResponse(200)]

        with patch("utils.reliability.requests.post", side_effect=responses) as mock_post, patch(
            "utils.reliability.time.sleep"
        ) as mock_sleep, patch("utils.reliability.random.uniform", return_value=0):
            resp = resilient_post(
                url="https://example.com",
                headers={"Authorization": "Bearer token"},
                payload={"ok": True},
                policy=policy,
                breaker_key="retry_success",
            )

        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)

    def test_resilient_post_honors_open_circuit_breaker(self):
        reliability._BREAKERS["blocked"] = CircuitBreaker(failure_threshold=1, reset_timeout_seconds=120)
        reliability._BREAKERS["blocked"].record_failure()

        with patch("utils.reliability.requests.post") as mock_post:
            resp = resilient_post(
                url="https://example.com",
                headers={},
                payload={},
                policy=RetryPolicy(max_attempts=2),
                breaker_key="blocked",
            )

        self.assertIsNone(resp)
        mock_post.assert_not_called()

    def test_api_auth_contract_public_vs_protected(self):
        with patch.dict("os.environ", {"RESCUENET_API_KEY": "secret"}, clear=False):
            client = TestClient(app)

            health = client.get("/health")
            self.assertEqual(health.status_code, 200)

            status_without_key = client.get("/status")
            self.assertEqual(status_without_key.status_code, 401)

            status_with_key = client.get("/status", headers={"x-api-key": "secret"})
            self.assertEqual(status_with_key.status_code, 200)

    def test_ops_metrics_endpoint_contract(self):
        update_state(
            {
                "ops_metrics": {
                    "ticks": 5,
                    "llm_triage_success": 3,
                    "llm_triage_fallback": 2,
                    "llm_dispatch_success": 1,
                    "llm_dispatch_fallback": 4,
                    "assignments_executed": 7,
                    "avg_tick_ms": 101.5,
                }
            }
        )

        with patch.dict("os.environ", {}, clear=False):
            client = TestClient(app)
            resp = client.get("/ops/metrics")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ticks"], 5)
        self.assertIn("avg_tick_ms", data)
        self.assertIn("assignments_executed", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
