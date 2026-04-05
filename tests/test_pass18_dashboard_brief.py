import unittest
from unittest.mock import patch

from dashboard.app import generate_ai_dashboard_brief
from state.fleet_state import FleetState


class _Env:
    tick = 1


class _SettingsNoKey:
    class deepseek:
        deepseek_api_key = ""
        deepseek_base_url = "https://example.com"
        deepseek_model = "model"


class _SettingsWithKey:
    class deepseek:
        deepseek_api_key = "abc123"
        deepseek_base_url = "https://example.com"
        deepseek_model = "model"


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


class TestDashboardBriefModes(unittest.TestCase):
    def test_brief_no_key_has_explicit_fallback_reason(self):
        env = _Env()
        fleet = FleetState(["drone_1"])
        with patch("dashboard.app.Settings", _SettingsNoKey):
            brief = generate_ai_dashboard_brief(env, fleet)
        self.assertEqual(brief.get("confidence"), "ai_unavailable_no_key")

    def test_brief_llm_unavailable_has_explicit_fallback_reason(self):
        env = _Env()
        fleet = FleetState(["drone_1"])
        with patch("dashboard.app.Settings", _SettingsWithKey), patch("dashboard.app.resilient_post", return_value=None):
            brief = generate_ai_dashboard_brief(env, fleet)
        self.assertEqual(brief.get("confidence"), "ai_unavailable_brief_timeout")
        self.assertTrue(brief.get("alerts"))

    def test_brief_timeout_does_not_depend_on_ai_decision_log(self):
        env = _Env()
        fleet = FleetState(["drone_1"])
        with patch("dashboard.app.Settings", _SettingsWithKey), patch("dashboard.app.resilient_post", return_value=None), patch("dashboard.app.load_ai_decisions") as mock_load_ai_decisions:
            brief = generate_ai_dashboard_brief(env, fleet)
        self.assertEqual(brief.get("confidence"), "ai_unavailable_brief_timeout")
        mock_load_ai_decisions.assert_not_called()

    def test_brief_parses_fenced_json_content(self):
        env = _Env()
        fleet = FleetState(["drone_1"])
        content = """```json
        {"headline":"Ops","priority_actions":["a","b","c"],"alerts":[]}
        ```"""
        payload = {"choices": [{"message": {"content": content}}]}
        with patch("dashboard.app.Settings", _SettingsWithKey), patch("dashboard.app.resilient_post", return_value=_FakeResponse(payload)):
            brief = generate_ai_dashboard_brief(env, fleet)
        self.assertEqual(brief.get("confidence"), "ai_live")
        self.assertEqual(brief.get("headline"), "Ops")

    def test_brief_handles_non_string_content_without_attribute_error(self):
        env = _Env()
        fleet = FleetState(["drone_1"])
        payload = {"choices": [{"message": {"content": None}}]}
        with patch("dashboard.app.Settings", _SettingsWithKey), patch("dashboard.app.resilient_post", return_value=_FakeResponse(payload)):
            brief = generate_ai_dashboard_brief(env, fleet)
        self.assertEqual(brief.get("confidence"), "ai_unavailable_brief_parse")


if __name__ == "__main__":
    unittest.main()
