import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from agents.policy_engine import PolicyConfig, PolicyEngine
from api.server import app
from state.fleet_state import FleetState, DroneStatus


class Pass7RegressionTests(unittest.TestCase):
    def test_policy_engine_blocks_low_battery_for_noncritical(self):
        fleet = FleetState(drone_names=["drone_1", "drone_2"])
        fleet.drones["drone_1"].battery = 15.0
        fleet.drones["drone_1"].status = DroneStatus.AVAILABLE
        fleet.drones["drone_2"].battery = 80.0
        fleet.drones["drone_2"].status = DroneStatus.AVAILABLE

        fleet.update_victim({"id": "victim_1", "triage_score": 70.0, "position": (1, 1, 0)})

        policy = PolicyEngine(PolicyConfig(min_battery_for_new_mission=25.0, min_reserve_available_drones=0))
        filtered = policy.filter_assignments(
            [
                {"drone_id": "drone_1", "victim_id": "victim_1"},
                {"drone_id": "drone_2", "victim_id": "victim_1"},
            ],
            fleet,
        )
        self.assertEqual(filtered, [{"drone_id": "drone_2", "victim_id": "victim_1"}])

    def test_policy_engine_critical_override_allows_reserve_break(self):
        fleet = FleetState(drone_names=["drone_1"])
        fleet.drones["drone_1"].battery = 90.0
        fleet.drones["drone_1"].status = DroneStatus.AVAILABLE
        fleet.update_victim({"id": "victim_critical", "triage_score": 99.0, "position": (2, 0, 0)})

        policy = PolicyEngine(
            PolicyConfig(min_battery_for_new_mission=25.0, min_reserve_available_drones=1, critical_override_score=90.0)
        )
        filtered = policy.filter_assignments(
            [{"drone_id": "drone_1", "victim_id": "victim_critical"}],
            fleet,
        )
        self.assertEqual(len(filtered), 1)

    def test_api_key_middleware_enforces_and_allows(self):
        with patch.dict("os.environ", {"RESCUENET_API_KEY": "secret-key"}, clear=False):
            client = TestClient(app)
            unauthorized = client.get("/status")
            self.assertEqual(unauthorized.status_code, 401)

            authorized = client.get("/status", headers={"x-api-key": "secret-key"})
            self.assertEqual(authorized.status_code, 200)

    def test_auth_status_endpoint_reflects_runtime_setting(self):
        with patch.dict("os.environ", {}, clear=False):
            client = TestClient(app)
            off = client.get("/security/auth-status")
            self.assertEqual(off.status_code, 200)
            self.assertFalse(off.json()["api_key_required"])

        with patch.dict("os.environ", {"RESCUENET_API_KEY": "on"}, clear=False):
            client = TestClient(app)
            on = client.get("/security/auth-status", headers={"x-api-key": "on"})
            self.assertEqual(on.status_code, 200)
            self.assertTrue(on.json()["api_key_required"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
