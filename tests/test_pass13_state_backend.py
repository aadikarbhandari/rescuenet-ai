import tempfile
import unittest

from fastapi.testclient import TestClient

import api.server as server
from state.fleet_state import DroneState
from utils.state_store import SQLiteStateStore


class Pass13StateBackendTests(unittest.TestCase):
    def test_update_state_persists_to_sqlite_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = server._db_store
            try:
                server._db_store = SQLiteStateStore.from_path(f"{tmp}/state.db")
                server.update_state({"tick": 9, "mode": "demo"})

                # simulate in-memory loss; durable store should still answer
                with server._state_lock:
                    server._state.pop("tick", None)
                    server._state.pop("mode", None)

                client = TestClient(server.app)
                health = client.get("/health")
                self.assertEqual(health.status_code, 200)
                body = health.json()
                self.assertEqual(body["tick"], 9)
                self.assertEqual(body["mode"], "demo")
            finally:
                server._db_store = original

    def test_update_state_serializes_dataclass_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = server._db_store
            try:
                server._db_store = SQLiteStateStore.from_path(f"{tmp}/state.db")
                server.update_state({"drones": [DroneState(id="drone_1")]})
                stored = server._db_store.get("drones", [])
                self.assertIsInstance(stored, list)
                self.assertEqual(stored[0]["id"], "drone_1")
            finally:
                server._db_store = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
