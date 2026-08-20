#!/usr/bin/env python3
import io
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("vibe_usage_helper", ROOT / "helper" / "usage.py")
assert spec is not None
assert spec.loader is not None
usage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = usage
spec.loader.exec_module(usage)


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now().astimezone().replace(microsecond=0)
        self.today = self.now.astimezone().date()
        self.today_stamp = f"{self.today.isoformat()}T12:00:00"
        self.yesterday_stamp = f"{(self.today - timedelta(days=1)).isoformat()}T12:00:00"

    def test_today_and_seven_day_windows(self):
        data = {
            "hasAnyData": True,
            "buckets": [
                {"source": "pi-coding-agent", "model": "gpt-5", "bucketStart": self.today_stamp,
                 "totalTokens": 1000, "estimatedCost": 1.25},
                {"source": "cursor", "model": "grok", "bucketStart": self.yesterday_stamp,
                 "totalTokens": 2000, "estimatedCost": 2.75},
            ],
            "sessions": [
                {"source": "pi-coding-agent", "lastMessageAt": self.today_stamp, "activeSeconds": 600},
                {"source": "cursor", "lastMessageAt": self.yesterday_stamp, "activeSeconds": 1200},
            ],
        }
        report = usage.build_report(data, {"apiUrl": "https://vibecafe.ai/", "hostname": "WorkOmarchy"}, now=self.now)
        today = report["windows"]["today"]
        seven = report["windows"]["7d"]

        self.assertEqual(today["totals"], {"cost": 1.25, "tokens": 1000, "sessions": 1, "activeSeconds": 600})
        self.assertEqual(seven["totals"], {"cost": 4, "tokens": 3000, "sessions": 2, "activeSeconds": 1800})
        self.assertEqual(today["byModel"][0]["name"], "gpt-5")
        self.assertEqual(today["bySource"][0]["name"], "pi")
        self.assertEqual(today["bySource"][0]["sessions"], 1)
        self.assertEqual(report["dashboard"], "https://vibecafe.ai/usage")
        self.assertEqual(report["hostname"], "WorkOmarchy")

    def test_top_eight_and_other(self):
        buckets = [
            {"source": f"tool-{i}", "model": f"model-{i}", "bucketStart": self.today_stamp,
             "totalTokens": i + 1, "estimatedCost": i + 1}
            for i in range(10)
        ]
        sessions = [
            {"source": f"tool-{i}", "lastMessageAt": self.today_stamp, "activeSeconds": 1}
            for i in range(10)
        ]
        window = usage.build_window(buckets, sessions, today=self.today, today_only=True)
        self.assertEqual(len(window["byModel"]), 9)
        self.assertEqual(window["byModel"][-1]["name"], "Other")
        self.assertEqual(window["byModel"][-1]["cost"], 3)
        self.assertEqual(window["byModel"][-1]["tokens"], 3)
        self.assertEqual(len(window["bySource"]), 9)
        self.assertEqual(window["bySource"][-1]["name"], "Other")
        self.assertEqual(window["bySource"][-1]["sessions"], 2)
        self.assertEqual(window["byModel"][-1]["pct"], 5)

    def test_auth_failure_does_not_return_key(self):
        key = "vbu_secret_for_test"

        def opener(_request, timeout):
            self.assertEqual(timeout, 15)
            raise HTTPError("https://vibecafe.ai/api/usage?days=7", 401, "unauthorized", cast(Any, {}), io.BytesIO())

        with self.assertRaises(usage.AuthenticationError) as raised:
            usage.fetch_usage({"apiUrl": "https://vibecafe.ai", "apiKey": key}, opener=opener)
        self.assertEqual(str(raised.exception), usage.AUTH_ERROR)
        self.assertNotIn(key, str(raised.exception))

    def test_missing_key_is_fixed_error(self):
        with self.assertRaises(usage.UsageError) as raised:
            usage.fetch_usage({"apiUrl": "https://vibecafe.ai"})
        self.assertEqual(str(raised.exception), usage.MISSING_KEY_ERROR)

    def test_fetch_success_sends_auth_header_and_days(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            seen["timeout"] = timeout
            return FakeResponse({"buckets": [], "sessions": []})

        result = usage.fetch_usage({"apiUrl": "https://example.test/", "apiKey": "vbu_test"}, opener=opener)
        self.assertEqual(result, {"buckets": [], "sessions": []})
        self.assertEqual(seen["url"], "https://example.test/api/usage?days=7")
        self.assertEqual(seen["auth"], "Bearer vbu_test")
        self.assertEqual(seen["timeout"], 15)

        usage.fetch_usage(
            {"apiUrl": "https://example.test/", "apiKey": "vbu_test"},
            opener=opener,
            days=1,
        )
        self.assertEqual(seen["url"], "https://example.test/api/usage?days=1")

    def test_today_uses_local_date_of_hourly_utc_buckets(self):
        local_tz = self.now.tzinfo
        midnight = datetime.combine(self.today, datetime.min.time(), tzinfo=local_tz)
        hour_today = (midnight + timedelta(hours=1)).astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        hour_yesterday = (midnight - timedelta(hours=1)).astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        utc_day_stamp = f"{self.today.isoformat()}T00:00:00.000Z"
        today_data = {
            "buckets": [
                {"source": "codex", "model": "gpt", "bucketStart": hour_today,
                 "totalTokens": 100, "estimatedCost": 10},
                {"source": "codex", "model": "gpt", "bucketStart": hour_yesterday,
                 "totalTokens": 200, "estimatedCost": 20},
            ],
            "sessions": [
                {"source": "codex", "lastMessageAt": hour_today, "activeSeconds": 30},
                {"source": "codex", "lastMessageAt": hour_yesterday, "activeSeconds": 90},
            ],
        }
        week_data = {
            "buckets": [
                {"source": "codex", "model": "gpt", "bucketStart": utc_day_stamp,
                 "totalTokens": 50, "estimatedCost": 1},
            ],
            "sessions": [],
        }
        report = usage.build_report(
            week_data,
            {"apiUrl": "https://vibecafe.ai", "hostname": "WorkOmarchy"},
            now=self.now,
            today_data=today_data,
        )
        today = report["windows"]["today"]
        self.assertEqual(today["totals"]["cost"], 10)
        self.assertEqual(today["totals"]["tokens"], 100)
        self.assertEqual(today["totals"]["sessions"], 1)
        self.assertEqual(report["windows"]["7d"]["totals"]["cost"], 1)


if __name__ == "__main__":
    unittest.main()
