"""
The perception component analyzes RGB and thermal camera feeds and identifies people using vision models. 
When a person is detected, it returns the world position of the victim.

AirSim camera → YOLOv8 → victim detection
"""

import airsim
import numpy as np
from ultralytics import YOLO

class PerceptionAgent:
    def __init__(self):
        # Initialize the AirSim client and a detection model:
        self.client = airsim.MultirotorClient()
        self.client.confirmConnection()
        self.model = YOLO("yolov8n.pt")

    # Capture images from drone cameras (returns a numpy image frame):
    def get_camera_image(self, drone_id):
        responses = self.client.simGetImages(
            [airsim.ImageRequest("0", airsim.ImageType.Scene, False, False)],
            vehicle_name=drone_id
        )

        img1d = np.frombuffer(responses[0].image_data_uint8, dtype=np.uint8)

        img = img1d.reshape(
            responses[0].height,
            responses[0].width,
            3
        )

        return img


    # Detect victims in the image (Each detection contains a bounding box for a detected person):
    def detect_victims(self, drone_id):
        img = self.get_camera_image(drone_id)

        results = self.model(img)
        victims = []

        for box in results[0].boxes:
            label = int(box.cls[0])

            if label == 0:   # person class
                victims.append({
                    "x": float(box.xyxy[0][0]),
                    "y": float(box.xyxy[0][1])
                })
                """# Combine detection + position
                bbox = box.xyxy[0].tolist()
                pos = self.estimate_world_position(drone_id, bbox)
                victims.append({
                    "drone": drone_id,
                    "position": pos
                })"""

        return victims
    

    # Convert detections to world coordinates:
    def estimate_world_position(self, drone_id, bbox):
        state = self.client.getMultirotorState(vehicle_name=drone_id)

        drone_pos = state.kinematics_estimated.position

        return {
            "x": drone_pos.x_val,
            "y": drone_pos.y_val,
            "z": drone_pos.z_val
        }
    

    # Scan using all drones:
    def scan_fleet(self, drone_ids):
        detections = []

        for drone in drone_ids:
            victims = self.detect_victims(drone)
            detections.extend(victims)

        return detections