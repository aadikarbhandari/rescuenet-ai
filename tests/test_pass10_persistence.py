import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.server import app
from utils.persistence import RuntimeStore


class Pass10PersistenceTests(unittest.TestCase):
    def test_runtime_store_snapshot_roundtrip_and_event_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RuntimeStore.from_path(tmp)

            store.save_snapshot({"tick": 7, "ops_metrics": {"avg_tick_ms": 12.5}})
            store.append_event("tick_persisted", {"tick": 7})
            store.append_event("tick_persisted", {"tick": 8})

            snapshot = store.load_snapshot()
            events = store.tail_events(limit=2)

            self.assertEqual(snapshot["tick"], 7)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[-1]["payload"]["tick"], 8)

    def test_ops_events_endpoint_reads_from_runtime_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RuntimeStore.from_path(tmp)
            store.append_event("tick_persisted", {"tick": 1, "assignments": 2})
            store.append_event("tick_persisted", {"tick": 2, "assignments": 1})

            with patch.dict(os.environ, {"RESCUENET_RUNTIME_DIR": tmp}, clear=False):
                client = TestClient(app)
                response = client.get("/ops/events?limit=1")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["payload"]["tick"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
