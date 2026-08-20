#!/usr/bin/env python3
import io
import importlib.util
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from typing import Any, cast

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
        self.timezone_name = "Asia/Shanghai"
        self.now = datetime.fromisoformat("2026-08-20T10:40:00+08:00")

    def test_today_report_aggregates_totals_series_and_groups(self):
        data = {
            "hasAnyData": True,
            "buckets": [
                {"source": "pi-coding-agent", "model": "gpt-5", "hostname": "Work",
                 "bucketStart": "2026-08-20T01:00:00+08:00", "totalTokens": 1000,
                 "cachedInputTokens": 250, "estimatedCost": 1.25},
                {"source": "cursor", "model": "grok", "hostname": "Home",
                 "bucketStart": "2026-08-20T01:00:00+08:00", "totalTokens": 2000,
                 "cachedInputTokens": 500, "estimatedCost": 2.75},
                {"source": "pi-coding-agent", "model": "gpt-5", "hostname": "Work",
                 "bucketStart": "2026-08-20T02:00:00+08:00", "totalTokens": 300,
                 "cachedInputTokens": 100, "estimatedCost": 1},
            ],
            "sessions": [
                {"source": "pi-coding-agent", "hostname": "Work", "activeSeconds": 600},
                {"source": "cursor", "hostname": "Home", "activeSeconds": 1200},
            ],
        }
        report = usage.build_report(
            data,
            {"apiUrl": "https://vibecafe.ai/", "hostname": "WorkOmarchy"},
            range_name="today",
            now=self.now,
            timezone_name=self.timezone_name,
        )

        self.assertEqual(report["range"], "today")
        self.assertEqual(report["totals"], {
            "cost": 5,
            "tokens": 3300,
            "cachedTokens": 850,
            "sessions": 2,
            "activeSeconds": 1800,
        })
        self.assertEqual(report["series"], [
            {"key": "2026-08-20T01:00:00+08:00", "label": "01:00", "cost": 4, "tokens": 3000},
            {"key": "2026-08-20T02:00:00+08:00", "label": "02:00", "cost": 1, "tokens": 300},
        ])
        self.assertEqual(report["bySource"][0]["name"], "cursor")
        self.assertEqual(report["bySource"][1]["name"], "pi")
        self.assertEqual(report["bySource"][0]["sessions"], 1)
        self.assertEqual(report["byHost"][0]["name"], "Home")
        self.assertEqual(report["byModel"][0]["name"], "grok")
        self.assertEqual(report["dashboard"], "https://vibecafe.ai/usage")

    def test_daily_series_uses_calendar_date_labels(self):
        data = {
            "buckets": [
                {"source": "codex", "model": "gpt", "hostname": "Work",
                 "bucketStart": "2026-08-18T00:00:00.000Z", "totalTokens": 100,
                 "estimatedCost": 1},
                {"source": "codex", "model": "gpt", "hostname": "Work",
                 "bucketStart": "2026-08-19T00:00:00.000Z", "totalTokens": 200,
                 "estimatedCost": 2},
            ],
            "sessions": [],
        }
        report = usage.build_report(
            data, {"apiUrl": "https://example.test"}, range_name="7d",
            now=self.now, timezone_name=self.timezone_name,
        )
        self.assertEqual([point["label"] for point in report["series"]], ["2026-08-18", "2026-08-19"])
        self.assertEqual(report["totals"]["tokens"], 300)

    def test_top_eight_and_other(self):
        buckets = [
            {"source": f"tool-{i}", "model": f"model-{i}", "hostname": f"host-{i}",
             "bucketStart": "2026-08-20T01:00:00+08:00", "totalTokens": i + 1,
             "estimatedCost": i + 1}
            for i in range(10)
        ]
        sessions = [
            {"source": f"tool-{i}", "hostname": f"host-{i}", "activeSeconds": 1}
            for i in range(10)
        ]
        window = usage.build_window(
            buckets, sessions, range_name="today", timezone_name=self.timezone_name
        )
        self.assertEqual(len(window["byModel"]), 9)
        self.assertEqual(window["byModel"][-1]["name"], "Other")
        self.assertEqual(window["byModel"][-1]["cost"], 3)
        self.assertEqual(window["byModel"][-1]["tokens"], 3)
        self.assertEqual(len(window["bySource"]), 9)
        self.assertEqual(window["bySource"][-1]["name"], "Other")
        self.assertEqual(window["bySource"][-1]["sessions"], 2)
        self.assertEqual(window["byModel"][-1]["pct"], 5)

    def test_fetch_query_has_one_request_and_local_timezone(self):
        seen = []

        def opener(request, timeout):
            seen.append({
                "url": request.full_url,
                "auth": request.get_header("Authorization"),
                "timeout": timeout,
            })
            return FakeResponse({"buckets": [], "sessions": []})

        config = {"apiUrl": "https://example.test/", "apiKey": "vbu_test"}
        usage.fetch_usage(
            config, opener=opener, range_name="today", now=self.now,
            timezone_name=self.timezone_name,
        )
        query = parse_qs(urlsplit(seen[-1]["url"]).query)
        self.assertEqual(query["from"], ["2026-08-19T16:00:00Z"])
        self.assertEqual(query["tz"], [self.timezone_name])

        for range_name, days in (("24h", "1"), ("7d", "7"), ("30d", "30")):
            usage.fetch_usage(
                config, opener=opener, range_name=range_name, now=self.now,
                timezone_name=self.timezone_name,
            )
            query = parse_qs(urlsplit(seen[-1]["url"]).query)
            self.assertEqual(query["days"], [days])
            self.assertEqual(query["tz"], [self.timezone_name])

        self.assertEqual(len(seen), 4)
        self.assertEqual(seen[0]["auth"], "Bearer vbu_test")
        self.assertEqual(seen[0]["timeout"], 15)

    def test_auth_failure_does_not_return_key(self):
        key = "vbu_secret_for_test"

        def opener(_request, timeout):
            self.assertEqual(timeout, 15)
            raise HTTPError(
                "https://vibecafe.ai/api/usage?days=7", 401, "unauthorized",
                cast(Any, {}), io.BytesIO(),
            )

        with self.assertRaises(usage.AuthenticationError) as raised:
            usage.fetch_usage(
                {"apiUrl": "https://vibecafe.ai", "apiKey": key},
                opener=opener, range_name="7d", timezone_name=self.timezone_name,
            )
        self.assertEqual(str(raised.exception), usage.AUTH_ERROR)
        self.assertNotIn(key, str(raised.exception))

    def test_missing_key_is_fixed_error(self):
        with self.assertRaises(usage.UsageError) as raised:
            usage.fetch_usage({"apiUrl": "https://vibecafe.ai"})
        self.assertEqual(str(raised.exception), usage.MISSING_KEY_ERROR)


if __name__ == "__main__":
    unittest.main()
