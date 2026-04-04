import unittest

from config.settings import Settings
from dashboard.app import _station_panel_data
from simulation.factory import SimulationFactory
from simulation.mock_env import MockDisasterEnv


class TestDemoScaling(unittest.TestCase):
    def test_demo_env_supports_large_drone_count(self):
        env = MockDisasterEnv(seed=42, num_drones=30, num_victims=4)
        self.assertEqual(len(env.get_drone_snapshots()), 30)
        self.assertEqual(len(env.get_victim_snapshots()), 4)

    def test_demo_env_supports_large_victim_count(self):
        env = MockDisasterEnv(seed=42, num_drones=4, num_victims=7)
        self.assertEqual(len(env.get_drone_snapshots()), 4)
        self.assertEqual(len(env.get_victim_snapshots()), 7)

    def test_factory_uses_mock_scaling_settings(self):
        settings = Settings()
        settings.mode = "demo"
        settings.mock_num_drones = 14
        settings.mock_num_victims = 9
        env = SimulationFactory.create(settings)
        self.assertEqual(len(env.get_drone_snapshots()), 14)
        self.assertEqual(len(env.get_victim_snapshots()), 9)

    def test_runtime_add_drone_and_victim(self):
        env = MockDisasterEnv(seed=42, num_drones=3, num_victims=4)
        d_id = env.add_drone()
        v_id = env.add_victim()
        self.assertEqual(d_id, "drone_4")
        self.assertEqual(v_id, "victim_5")
        self.assertEqual(len(env.get_drone_snapshots()), 4)
        self.assertEqual(len(env.get_victim_snapshots()), 5)

    def test_station_panel_uses_env_data(self):
        env = MockDisasterEnv(seed=42, num_drones=3, num_victims=4)
        rows = _station_panel_data(env)
        self.assertTrue(len(rows) >= 1)
        self.assertIn("Station", rows[0])
        self.assertIn("Supplies Remaining", rows[0])

    def test_mock_station_status_reflects_charging(self):
        env = MockDisasterEnv(seed=42, num_drones=3, num_victims=4)
        env.drones[0]["operational_status"] = "charging"
        status = env.get_station_status()
        self.assertTrue(len(status) >= 1)
        self.assertIn("drone_1", status[0].get("drones_present", []))


if __name__ == "__main__":
    unittest.main()
