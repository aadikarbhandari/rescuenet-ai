import unittest

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


if __name__ == "__main__":
    unittest.main()
