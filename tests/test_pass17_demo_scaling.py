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

    def test_station_add_remove_and_supply_update(self):
        env = MockDisasterEnv(seed=42, num_drones=3, num_victims=4)
        added = env.add_station("Station Delta")
        self.assertEqual(added, "Station Delta")
        self.assertTrue(env.update_station_supplies("Station Delta", 10, 20, 30))
        stations = env.get_station_status()
        delta = next(s for s in stations if s["name"] == "Station Delta")
        self.assertEqual(delta["supplies"]["first_aid_kit"], 10)
        self.assertEqual(delta["supplies"]["water"], 20)
        self.assertEqual(delta["supplies"]["food"], 30)
        self.assertTrue(env.remove_station("Station Delta"))

    def test_victim_marked_rescued_on_mission_completion(self):
        env = MockDisasterEnv(seed=42, num_drones=3, num_victims=4)
        before = env.get_station_status()[0]["supplies"]["first_aid_kit"]
        mission_id = "mission_test_1"
        victim_id = env.victims[0]["victim_id"]
        env.update_victim_assignment(victim_id, "drone_1", mission_id)
        env.update_drone_mission("drone_1", mission_id)
        env.drones[0]["position"] = env.victims[0]["position"]
        env.drones[0]["operational_status"] = "on_scene"
        env.active_missions[mission_id] = {"start_tick": env.tick - 5, "duration_ticks": 1, "drone_id": "drone_1", "target_id": victim_id}
        env.step()
        victim = next(v for v in env.victims if v["victim_id"] == victim_id)
        self.assertEqual(victim.get("status"), "rescued")
        after = env.get_station_status()[0]["supplies"]["first_aid_kit"]
        self.assertLessEqual(after, before)


if __name__ == "__main__":
    unittest.main()
