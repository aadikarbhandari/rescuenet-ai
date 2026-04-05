import hashlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.server as server


class Pass12ApiHardeningTests(unittest.TestCase):
    def setUp(self):
        server._rate_state.clear()

    def test_sha256_api_key_mode_accepts_plain_client_key(self):
        secret = "my-secret"
        digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()

        with patch.dict(os.environ, {"RESCUENET_API_KEY": f"sha256:{digest}"}, clear=False):
            client = TestClient(server.app)
            unauthorized = client.get("/status")
            self.assertEqual(unauthorized.status_code, 401)

            authorized = client.get("/status", headers={"x-api-key": secret})
            self.assertEqual(authorized.status_code, 200)

    def test_rate_limit_blocks_excess_requests(self):
        with patch.dict(
            os.environ,
            {
                "RESCUENET_API_KEY": "secret",
                "RESCUENET_RATE_LIMIT_PER_MIN": "2",
            },
            clear=False,
        ):
            client = TestClient(server.app)
            h = {"x-api-key": "secret"}
            r1 = client.get("/status", headers=h)
            r2 = client.get("/status", headers=h)
            r3 = client.get("/status", headers=h)

            self.assertEqual(r1.status_code, 200)
            self.assertEqual(r2.status_code, 200)
            self.assertEqual(r3.status_code, 429)


if __name__ == "__main__":
    unittest.main(verbosity=2)
