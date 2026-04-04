import tempfile
import unittest

from fastapi.testclient import TestClient

import api.server as server
from utils.task_queue import SQLiteTaskQueue


class Pass14TaskQueueTests(unittest.TestCase):
    def test_queue_lifecycle_claim_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = SQLiteTaskQueue(f"{tmp}/queue.db")
            tid = q.enqueue(kind="noop", payload={"a": 1})
            task = q.claim_next()
            self.assertIsNotNone(task)
            self.assertEqual(task.task_id, tid)
            q.complete(tid)
            tasks = q.list_tasks(limit=5)
            self.assertEqual(tasks[0]["status"], "done")

    def test_api_queue_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = server._task_queue
            try:
                server._task_queue = SQLiteTaskQueue(f"{tmp}/queue.db")
                client = TestClient(server.app)

                enq = client.post("/ops/tasks/enqueue", json={"kind": "noop", "payload": {"x": 1}})
                self.assertEqual(enq.status_code, 200)
                task_id = enq.json()["task_id"]

                claim = client.post("/ops/tasks/claim")
                self.assertEqual(claim.status_code, 200)
                self.assertEqual(claim.json()["task"]["task_id"], task_id)

                done = client.post(f"/ops/tasks/{task_id}/complete")
                self.assertEqual(done.status_code, 200)

                listing = client.get("/ops/tasks")
                self.assertEqual(listing.status_code, 200)
                self.assertTrue(any(t["task_id"] == task_id for t in listing.json()))
            finally:
                server._task_queue = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
