import unittest
from unittest.mock import patch

from config.settings import Settings, RuntimeMode
from simulation.factory import SimulationFactory


class TestModeCompatibility(unittest.TestCase):
    def test_factory_accepts_airsim_alias(self):
        settings = Settings()
        settings.mode = RuntimeMode.AIRSIM
        with patch.object(SimulationFactory, "_create_airsim", return_value="airsim-env") as mocked:
            out = SimulationFactory.create(settings)
        self.assertEqual(out, "airsim-env")
        mocked.assert_called_once()

    def test_factory_accepts_sim_mode(self):
        settings = Settings()
        settings.mode = RuntimeMode.SIM
        with patch.object(SimulationFactory, "_create_airsim", return_value="sim-env") as mocked:
            out = SimulationFactory.create(settings)
        self.assertEqual(out, "sim-env")
        mocked.assert_called_once()

    def test_factory_accepts_string_mode(self):
        settings = Settings()
        settings.mode = "airsim"
        with patch.object(SimulationFactory, "_create_airsim", return_value="airsim-env") as mocked:
            out = SimulationFactory.create(settings)
        self.assertEqual(out, "airsim-env")
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
