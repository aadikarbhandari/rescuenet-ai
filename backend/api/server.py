"""
API FastAPI pour communiquer avec Next.js
Lancer le backend : cd backend -> venv\Scripts\activate -> uvicorn api.server:app --reload --port 8000
API disponible sur : http://localhost:8000/fleet-state
Lancer le frontend : cd frontend -> npm run dev
Frontend et dashboard disponibles sur : http://localhost:3000
"""

from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse
import asyncio
import airsim
import cv2
import numpy as np

from agents.state_awareness import StateAwarenessAgent
from agents.perception import PerceptionAgent

app = FastAPI()



# --------------------------------------------------
# Agents
# --------------------------------------------------

state_agent = StateAwarenessAgent(update_interval=1.0)
state_agent.start()

perception_agent = PerceptionAgent()

# AirSim connection
client = airsim.MultirotorClient()
client.confirmConnection()


# --------------------------------------------------
# Helper functions
# --------------------------------------------------

def get_drones_data():
    fleet_state = state_agent.get_fleet_state()
    return fleet_state.get_all_drones_dict(client)


def get_victims_data():
    fleet_state = state_agent.get_fleet_state()
    drone_ids = [drone.drone_id for drone in fleet_state.get_all_drones()]

    """victims = []
    for drone in fleet_state.get_all_drones():
        detections = perception_agent.detect_victims(drone.drone_id)
        victims.extend(detections)
    return victims"""

    return perception_agent.scan_fleet(drone_ids)

    


def get_paths():
    paths = []

    fleet_state = state_agent.get_fleet_state()

    for drone in fleet_state.get_all_drones():
        pos = drone.position

        path = [
            [pos[0], pos[1], 0],
            [pos[0] + 10, pos[1] + 5, 0],
            [pos[0] + 20, pos[1] + 10, 0]
        ]

        paths.append(path)

    return paths


def get_agents_status():
    return {
        "state_awareness": True,
        "perception": True,
        "routing": True,
        "triage": True,
        "coordinator": True,
        "voice": True,
        "security": True
    }


# --------------------------------------------------
# REST endpoint (debugging / testing)
# --------------------------------------------------

@app.get("/fleet-state-api")
async def get_fleet_state():
    drones = get_drones_data()
    victims = get_victims_data()
    paths = get_paths()
    agents = get_agents_status()

    return {
        "drones": drones,
        "victims": victims,
        "paths": paths,
        "agents": agents
    }


# --------------------------------------------------
# WebSocket stream (real-time dashboard)
# --------------------------------------------------

@app.websocket("/fleet-state")
async def fleet_stream(websocket: WebSocket):
    await websocket.accept()

    while True:
        drones = get_drones_data()
        victims = get_victims_data()
        paths = get_paths()
        agents = get_agents_status()

        await websocket.send_json({
            "drones": drones,
            "victims": victims,
            "paths": paths,
            "agents": agents
        })

        await asyncio.sleep(1)


# --------------------------------------------------
# Drone camera streaming
# --------------------------------------------------

def camera_stream(vehicle_name):
    while True:
        responses = client.simGetImages([
            airsim.ImageRequest("0", airsim.ImageType.Scene, False, False)
        ], vehicle_name=vehicle_name)

        img1d = np.frombuffer(responses[0].image_data_uint8, dtype=np.uint8)

        img = img1d.reshape(
            responses[0].height,
            responses[0].width,
            3
        )

        _, jpeg = cv2.imencode(".jpg", img)

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            jpeg.tobytes() +
            b"\r\n"
        )


@app.get("/drone_feed/{drone_id}")
def drone_feed(drone_id: str):
    return StreamingResponse(
        camera_stream(drone_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )