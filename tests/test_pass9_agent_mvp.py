import unittest

from agents.perception import PerceptionAgent
from agents.routing import RoutingAgent


class Pass9AgentMVPTests(unittest.TestCase):
    def test_perception_prefers_closer_sensor_rich_drone(self):
        perception = PerceptionAgent(detection_radius=60.0, confirmation_confidence=0.65)
        drones = [
            {"drone_id": "drone_far", "position": (40.0, 0.0, 0.0), "sensors": {"camera": True}},
            {"drone_id": "drone_near", "position": (5.0, 0.0, 0.0), "sensors": {"camera": True, "thermal": True}},
        ]
        victims = [{"victim_id": "victim_1", "position": (0.0, 0.0, 0.0)}]

        detections = perception.detect_victims(drones, victims)
        self.assertEqual(len(detections), 1)
        self.assertTrue(detections[0]["detected"])
        self.assertGreaterEqual(detections[0]["confidence"], 0.65)
        self.assertEqual(detections[0]["detected_by"], "drone_near")

    def test_perception_returns_undetected_when_out_of_range(self):
        perception = PerceptionAgent(detection_radius=10.0)
        drones = [{"drone_id": "drone_1", "position": (100.0, 0.0, 0.0), "sensors": {"camera": True}}]
        victims = [{"victim_id": "victim_1", "position": (0.0, 0.0, 0.0)}]

        detections = perception.detect_victims(drones, victims)
        self.assertEqual(detections[0]["detected"], False)
        self.assertEqual(detections[0]["detected_by"], "none")

    def test_routing_generates_direct_safe_altitude_route(self):
        routing = RoutingAgent(safety_altitude_m=30.0)
        route = routing.plan_route(
            drone_id="drone_1",
            start=(0.0, 0.0, 0.0),
            target=(100.0, 0.0, 0.0),
            jam_detected=False,
        )
        self.assertEqual(route["mode"], "direct_safe_altitude")
        self.assertEqual(len(route["waypoints"]), 3)
        self.assertGreater(route["distance_m"], 0)

    def test_routing_switches_to_jam_fallback_mode(self):
        routing = RoutingAgent(safety_altitude_m=25.0)
        route = routing.plan_route(
            drone_id="drone_1",
            start=(10.0, 0.0, 0.0),
            target=(100.0, 100.0, 0.0),
            jam_detected=True,
            return_base=(0.0, 0.0, 0.0),
        )
        self.assertEqual(route["mode"], "jam_fallback_rtb")
        self.assertEqual(route["waypoints"][-1], (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
