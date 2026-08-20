#!/usr/bin/env python3
import io
import importlib.util
import json
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from typing import Any, cast
from unittest.mock import patch

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
                 "bucketStart": "2026-08-20T01:00:00+08:00", "totalTokens": 999,
                 "inputTokens": 600, "outputTokens": 100,
                 "reasoningOutputTokens": 50, "cachedInputTokens": 250,
                 "estimatedCost": 1.25},
                {"source": "cursor", "model": "grok", "hostname": "Home",
                 "bucketStart": "2026-08-20T01:00:00+08:00", "totalTokens": 1,
                 "inputTokens": 1000, "outputTokens": 500,
                 "reasoningOutputTokens": 250, "cachedInputTokens": 500,
                 "estimatedCost": 2.75},
                {"source": "pi-coding-agent", "model": "gpt-5", "hostname": "Work",
                 "bucketStart": "2026-08-20T02:00:00+08:00", "totalTokens": 999,
                 "inputTokens": 100, "outputTokens": 50,
                 "reasoningOutputTokens": 50, "cachedInputTokens": 100,
                 "estimatedCost": 1},
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
            "tokens": 3550,
            "cachedTokens": 850,
            "sessions": 2,
            "activeSeconds": 1800,
        })
        self.assertEqual(report["series"], [
            {"key": "2026-08-20T01:00:00+08:00", "label": "01:00", "cost": 4, "tokens": 3250},
            {"key": "2026-08-20T02:00:00+08:00", "label": "02:00", "cost": 1, "tokens": 300},
        ])
        self.assertEqual(report["bySource"][0]["name"], "cursor")
        self.assertEqual(report["bySource"][0]["tokens"], 2250)
        self.assertEqual(report["bySource"][1]["name"], "pi")
        self.assertEqual(report["bySourceTokens"][0]["name"], "cursor")
        self.assertEqual(report["bySourceTokens"][1]["name"], "pi")
        self.assertEqual(report["bySourceTokens"][0]["pct"], 63)
        self.assertEqual(report["byHostTokens"][0]["name"], "Home")
        self.assertEqual(report["byModelTokens"][0]["name"], "grok")
        self.assertEqual(report["bySource"][0]["sessions"], 1)
        self.assertEqual(report["byHost"][0]["name"], "Home")
        self.assertEqual(report["byModel"][0]["name"], "grok")
        self.assertEqual(report["dashboard"], "https://vibecafe.ai/usage")

    def test_daily_series_uses_calendar_date_labels(self):
        data = {
            "buckets": [
                {"source": "codex", "model": "gpt", "hostname": "Work",
                 "bucketStart": "2026-08-18T00:00:00.000Z", "totalTokens": 1,
                 "inputTokens": 40, "outputTokens": 30,
                 "reasoningOutputTokens": 10, "cachedInputTokens": 20,
                 "estimatedCost": 1},
                {"source": "codex", "model": "gpt", "hostname": "Work",
                 "bucketStart": "2026-08-19T00:00:00.000Z", "totalTokens": 2,
                 "inputTokens": 80, "outputTokens": 50,
                 "reasoningOutputTokens": 20, "cachedInputTokens": 50,
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

    def test_component_token_fallback_uses_billed_plus_cache(self):
        bucket = {
            "source": "codex",
            "model": "gpt",
            "hostname": "Work",
            "bucketStart": "2026-08-20T03:00:00+08:00",
            "totalTokens": 700,
            "cachedInputTokens": 100,
            "estimatedCost": 1,
        }
        report = usage.build_report(
            {"buckets": [bucket], "sessions": []},
            {"apiUrl": "https://example.test"},
            range_name="today",
            now=self.now,
            timezone_name=self.timezone_name,
        )
        self.assertEqual(report["totals"]["tokens"], 800)
        self.assertEqual(report["series"][0]["tokens"], 800)
        self.assertEqual(report["byModel"][0]["tokens"], 800)

    def test_cost_and_token_rankings_are_independent(self):
        buckets = [
            {"source": "expensive", "model": "expensive", "hostname": "expensive",
             "bucketStart": "2026-08-20T01:00:00+08:00", "inputTokens": 100,
             "outputTokens": 0, "reasoningOutputTokens": 0, "cachedInputTokens": 0,
             "estimatedCost": 9},
            {"source": "high-volume", "model": "high-volume", "hostname": "high-volume",
             "bucketStart": "2026-08-20T02:00:00+08:00", "inputTokens": 10000,
             "outputTokens": 0, "reasoningOutputTokens": 0, "cachedInputTokens": 0,
             "estimatedCost": 1},
        ]
        window = usage.build_window(
            buckets, [], range_name="today", timezone_name=self.timezone_name
        )

        self.assertEqual([row["name"] for row in window["bySource"]], [
            "expensive", "high-volume"
        ])
        self.assertEqual([row["name"] for row in window["bySourceTokens"]], [
            "high-volume", "expensive"
        ])
        self.assertEqual(window["bySource"][0]["pct"], 90)
        self.assertEqual(window["bySourceTokens"][0]["pct"], 99)
        self.assertEqual(window["byModelTokens"][0]["name"], "high-volume")
        self.assertEqual(window["byHostTokens"][0]["name"], "high-volume")

    def test_token_top_eight_and_other_are_independent(self):
        buckets = [
            {"source": f"tool-{i}", "model": f"model-{i}", "hostname": f"host-{i}",
             "bucketStart": "2026-08-20T01:00:00+08:00", "inputTokens": 10000 - i * 100,
             "outputTokens": 0, "reasoningOutputTokens": 0, "cachedInputTokens": 0,
             "estimatedCost": i + 1}
            for i in range(10)
        ]
        window = usage.build_window(
            buckets, [], range_name="today", timezone_name=self.timezone_name
        )

        self.assertEqual([row["name"] for row in window["byModel"]], [
            "model-9", "model-8", "model-7", "model-6", "model-5",
            "model-4", "model-3", "model-2", "Other",
        ])
        self.assertEqual([row["name"] for row in window["byModelTokens"]], [
            "model-0", "model-1", "model-2", "model-3", "model-4",
            "model-5", "model-6", "model-7", "Other",
        ])
        self.assertEqual(window["byModel"][8]["tokens"], 19900)
        self.assertEqual(window["byModelTokens"][8]["cost"], 19)
        self.assertEqual(window["byModelTokens"][8]["tokens"], 18300)

    def test_top_eight_and_other(self):
        buckets = [
            {"source": f"tool-{i}", "model": f"model-{i}", "hostname": f"host-{i}",
             "bucketStart": "2026-08-20T01:00:00+08:00", "totalTokens": 999,
             "inputTokens": i + 1, "outputTokens": 0,
             "reasoningOutputTokens": 0, "cachedInputTokens": 0,
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
            error = HTTPError(
                "https://vibecafe.ai/api/usage?days=7", 401, "unauthorized",
                cast(Any, {}), None,
            )
            try:
                raise error
            finally:
                error.close()

        with self.assertRaises(usage.AuthenticationError) as raised:
            usage.fetch_usage(
                {"apiUrl": "https://vibecafe.ai", "apiKey": key},
                opener=opener, range_name="7d", timezone_name=self.timezone_name,
            )
        self.assertEqual(str(raised.exception), usage.AUTH_ERROR)
        self.assertEqual(raised.exception.code, usage.ERROR_AUTHENTICATION)
        self.assertNotIn(key, str(raised.exception))

    def test_missing_key_is_fixed_error(self):
        with self.assertRaises(usage.UsageError) as raised:
            usage.fetch_usage({"apiUrl": "https://vibecafe.ai"})
        self.assertEqual(str(raised.exception), usage.MISSING_KEY_ERROR)
        self.assertEqual(raised.exception.code, usage.ERROR_MISSING_API_KEY)

    def test_fetch_failures_have_stable_error_codes(self):
        config = {"apiUrl": "https://example.test", "apiKey": "vbu_test"}

        def http_failure(_request, timeout):
            error = HTTPError(
                "https://example.test/api/usage", 503, "unavailable",
                cast(Any, {}), None,
            )
            try:
                raise error
            finally:
                error.close()

        with self.assertRaises(usage.UsageError) as raised:
            usage.fetch_usage(config, opener=http_failure)
        self.assertEqual(raised.exception.code, usage.ERROR_HTTP)

        def network_failure(_request, timeout):
            raise URLError("offline")

        with self.assertRaises(usage.UsageError) as raised:
            usage.fetch_usage(config, opener=network_failure)
        self.assertEqual(raised.exception.code, usage.ERROR_NETWORK)

        invalid_json = FakeResponse({})
        invalid_json.payload = b"not json"
        with self.assertRaises(usage.UsageError) as raised:
            usage.fetch_usage(
                config,
                opener=lambda _request, timeout: invalid_json,
            )
        self.assertEqual(raised.exception.code, usage.ERROR_INVALID_JSON)

    def test_main_emits_stable_error_codes(self):
        output = io.StringIO()
        with patch.object(usage.sys, "argv", ["usage.py", "--range", "bad"]):
            with redirect_stdout(output):
                status = usage.main()
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.getvalue())["code"], usage.ERROR_INVALID_RANGE)

        output = io.StringIO()
        with patch.object(usage, "load_config", return_value=None):
            with patch.object(usage.sys, "argv", ["usage.py", "--range", "today"]):
                with redirect_stdout(output):
                    status = usage.main()
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.getvalue())["code"], usage.ERROR_MISSING_API_KEY)


if __name__ == "__main__":
    unittest.main()
