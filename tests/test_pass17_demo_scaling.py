import unittest

from config.settings import Settings
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


if __name__ == "__main__":
    unittest.main()
