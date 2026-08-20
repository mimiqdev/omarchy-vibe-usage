#!/usr/bin/env python3
"""Fetch and shape the Vibe Usage API response for the Omarchy widget.

The helper is deliberately a small, dependency-free process. It reads the
credential from vibe-usage's owner-only config file, performs one authenticated
7-day request, and writes exactly one JSON document to stdout. QML never sees
the API key and stale data remains the panel's responsibility.
"""

from __future__ import annotations

import json
import math
import os
import socket
import sys
from collections import OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

API_TIMEOUT_SECONDS = 15
DEFAULT_API_URL = "https://vibecafe.ai"
AUTH_ERROR = "API Key 无效，请运行 vibe-usage init"
MISSING_KEY_ERROR = "未配置 API Key，请运行 vibe-usage init"


class UsageError(Exception):
    """An expected, user-facing helper failure."""


class AuthenticationError(UsageError):
    """The API rejected the configured key."""


def config_path() -> Path:
    """Return the normal config path, with test-only path overrides."""
    explicit = os.environ.get("VIBE_USAGE_CONFIG_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    config_dir = os.environ.get("VIBE_USAGE_CONFIG_DIR", "").strip()
    if config_dir:
        return Path(config_dir).expanduser() / "config.json"
    return Path.home() / ".vibe-usage" / "config.json"


def load_config(path: Path | None = None) -> dict[str, Any] | None:
    """Load config.json without ever logging its contents."""
    try:
        raw = (path or config_path()).read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value).strip()


def _api_url(config: Mapping[str, Any]) -> str:
    value = (_text(config.get("apiUrl")) or DEFAULT_API_URL).rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise UsageError("配置中的 API 地址无效")
    return value


def dashboard_url(api_url: str) -> str:
    """Build the dashboard URL without duplicating a trailing slash."""
    return api_url.rstrip("/") + "/usage"


def _request_url(api_url: str, days: int) -> str:
    return api_url.rstrip("/") + f"/api/usage?days={days}"


def fetch_usage(
    config: Mapping[str, Any],
    opener: Callable[..., Any] | None = None,
    *,
    days: int = 7,
) -> Mapping[str, Any]:
    """Fetch the API report using the same endpoint as ``summary``.

    ``days=7`` is a UTC daily rollup. ``days=1`` is hourly and is what
    local-calendar "today" needs. ``opener`` is injectable for offline
    tests; the production path uses urllib with a 15-second timeout.
    """
    api_key = _text(config.get("apiKey"))
    if not api_key:
        raise UsageError(MISSING_KEY_ERROR)
    api_url = _api_url(config)
    window_days = days if days in {1, 7} else 7
    request = Request(
        _request_url(api_url, window_days),
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        method="GET",
    )
    open_request = opener or urlopen
    try:
        response = open_request(request, timeout=API_TIMEOUT_SECONDS)
        if hasattr(response, "__enter__"):
            with response as stream:
                body = stream.read()
        else:
            body = response.read()
    except HTTPError as error:
        if error.code == 401:
            raise AuthenticationError(AUTH_ERROR) from None
        raise UsageError(f"获取用量数据失败: HTTP {error.code}") from None
    except (URLError, TimeoutError, OSError) as error:
        message = _text(getattr(error, "reason", error), "网络请求失败")
        # urllib error text is not allowed to contain the credential. It does
        # not normally include headers, but this replacement is cheap defense
        # in depth for custom openers and future urllib changes.
        message = message.replace(api_key, "[redacted]")
        raise UsageError(f"获取用量数据失败: {message}") from None

    try:
        decoded = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
    except (UnicodeError, json.JSONDecodeError):
        raise UsageError("获取用量数据失败: API 返回了无效 JSON") from None
    if not isinstance(decoded, dict):
        raise UsageError("获取用量数据失败: API 返回格式无效")
    return decoded


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback


def _safe_round(value: Any, digits: int | None = None) -> int | float:
    try:
        return round(value) if digits is None else round(value, digits)
    except (TypeError, ValueError, OverflowError):
        return 0


def _non_negative(value: Any) -> float:
    return max(0.0, _number(value))


def _tidy(value: float) -> int | float:
    value = _non_negative(value)
    rounded = _safe_round(value)
    if abs(value - rounded) < 1e-9:
        return _safe_int(rounded)
    return _safe_round(value, 6)


def _cost(value: Any) -> float:
    return _non_negative(value)


def _tokens(value: Any) -> int | float:
    # totalTokens is an integer in the API. Preserve fractional test fixtures
    # rather than silently truncating malformed data, while normal responses
    # serialize as compact integers.
    return _tidy(_non_negative(value))


def _parse_instant(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            timestamp = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if math.isfinite(timestamp):
            if abs(timestamp) > 100_000_000_000:
                timestamp /= 1000
            try:
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
    text = _text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed


def local_date(value: Any) -> date | None:
    """Interpret an API instant in the machine's local calendar."""
    parsed = _parse_instant(value)
    if parsed is None:
        return None
    return parsed.astimezone().date()


def _today(now: datetime | None = None) -> date:
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return current.astimezone().date()


def _timestamp(now: datetime | None = None) -> str:
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return current.astimezone().isoformat(timespec="seconds")


def source_label(value: Any) -> str:
    source = _text(value, "unknown") or "unknown"
    return "pi" if source == "pi-coding-agent" else source


def item_label(value: Any) -> str:
    return _text(value, "unknown") or "unknown"


def _empty_group(include_sessions: bool = False) -> dict[str, int | float]:
    group: dict[str, int | float] = {"cost": 0, "tokens": 0}
    if include_sessions:
        group["sessions"] = 0
    return group


def _ensure_source(
    groups: OrderedDict[str, dict[str, int | float]], name: str
) -> dict[str, int | float]:
    if name not in groups:
        groups[name] = _empty_group(True)
    elif "sessions" not in groups[name]:
        groups[name]["sessions"] = 0
    return groups[name]


def _round_percent(value: float) -> int:
    # JavaScript's Math.round semantics for the non-negative cost values used
    # here (Python's round uses bankers' rounding at .5).
    try:
        rounded = int(math.floor(value + 0.5))
    except (TypeError, ValueError, OverflowError):
        rounded = 0
    return max(0, min(100, rounded))


def _ranked(
    groups: OrderedDict[str, dict[str, int | float]],
    total_cost: float,
    include_sessions: bool,
) -> list[dict[str, int | float | str]]:
    try:
        ranked = sorted(groups.items(), key=lambda item: (-_number(item[1].get("cost", 0)), item[0]))
    except (TypeError, ValueError):
        ranked = list(groups.items())
    if len(ranked) > 8:
        kept = ranked[:8]
        remainder = ranked[8:]
        other = _empty_group(include_sessions)
        for _, group in remainder:
            other["cost"] = _tidy(_number(other["cost"]) + _number(group.get("cost", 0)))
            other["tokens"] = _tokens(_number(other["tokens"]) + _number(group.get("tokens", 0)))
            if include_sessions:
                other["sessions"] = _safe_int(other["sessions"]) + _safe_int(group.get("sessions", 0))
        kept.append(("Other", other))
    else:
        kept = ranked

    rows: list[dict[str, int | float | str]] = []
    denominator = _cost(total_cost)
    for name, group in kept:
        cost = _tidy(_number(group.get("cost", 0)))
        row: dict[str, int | float | str] = {
            "name": name,
            "cost": cost,
            "tokens": _tokens(group.get("tokens", 0)),
        }
        if include_sessions:
            row["sessions"] = _safe_int(group.get("sessions", 0))
        row["pct"] = _round_percent(_number(cost) * 100 / denominator) if denominator > 0 else 0
        rows.append(row)
    return rows


def build_window(
    buckets: Iterable[Any],
    sessions: Iterable[Any],
    *,
    today: date | None = None,
    today_only: bool = False,
) -> dict[str, Any]:
    """Aggregate one API response window according to the plugin contract."""
    bucket_values = [bucket for bucket in buckets if isinstance(bucket, dict)]
    session_values = [session for session in sessions if isinstance(session, dict)]
    if today_only:
        target = today or _today()
        bucket_values = [b for b in bucket_values if local_date(b.get("bucketStart")) == target]
        session_values = [s for s in session_values if local_date(s.get("lastMessageAt")) == target]

    total_cost = 0.0
    total_tokens: int | float = 0
    by_model: OrderedDict[str, dict[str, int | float]] = OrderedDict()
    by_source: OrderedDict[str, dict[str, int | float]] = OrderedDict()

    for bucket in bucket_values:
        cost = _cost(bucket.get("estimatedCost"))
        tokens = _tokens(bucket.get("totalTokens"))
        total_cost += cost
        total_tokens = _tokens(_number(total_tokens) + _number(tokens))
        model = item_label(bucket.get("model"))
        source = source_label(bucket.get("source"))

        model_group = by_model.setdefault(model, _empty_group())
        model_group["cost"] = _tidy(_number(model_group["cost"]) + cost)
        model_group["tokens"] = _tokens(_number(model_group["tokens"]) + _number(tokens))

        source_group = _ensure_source(by_source, source)
        source_group["cost"] = _tidy(_number(source_group["cost"]) + cost)
        source_group["tokens"] = _tokens(_number(source_group["tokens"]) + _number(tokens))

    for session in session_values:
        source = source_label(session.get("source"))
        source_group = _ensure_source(by_source, source)
        source_group["sessions"] = _safe_int(source_group["sessions"]) + 1

    active_seconds = 0.0
    for session in session_values:
        active_seconds += _non_negative(session.get("activeSeconds"))

    return {
        "totals": {
            "cost": _tidy(total_cost),
            "tokens": total_tokens,
            "sessions": len(session_values),
            "activeSeconds": _tidy(active_seconds),
        },
        "byModel": _ranked(by_model, total_cost, False),
        "bySource": _ranked(by_source, total_cost, True),
    }


def _payload_lists(data: Mapping[str, Any] | None) -> tuple[list[Any], list[Any]]:
    if not isinstance(data, dict):
        raise UsageError("获取用量数据失败: API 返回格式无效")
    buckets = data.get("buckets")
    sessions = data.get("sessions")
    return (
        buckets if isinstance(buckets, list) else [],
        sessions if isinstance(sessions, list) else [],
    )


def build_report(
    data: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
    today_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn API responses into the stable JSON contract consumed by QML.

    ``today_data`` should be the hourly ``days=1`` payload so local midnight
    to now can be sliced. When omitted (tests), ``data`` is used for both
    windows.
    """
    week_buckets, week_sessions = _payload_lists(data)
    today_source = today_data if today_data is not None else data
    today_buckets, today_sessions = _payload_lists(today_source)

    local_today = _today(now)
    config = config or {}
    api_url = _api_url(config)
    hostname = _text(config.get("hostname")) or socket.gethostname()
    return {
        "ok": True,
        "fetchedAt": _timestamp(now),
        "dashboard": dashboard_url(api_url),
        "hostname": hostname,
        "windows": {
            "today": build_window(
                today_buckets, today_sessions, today=local_today, today_only=True
            ),
            "7d": build_window(week_buckets, week_sessions),
        },
    }


def emit(payload: Mapping[str, Any]) -> None:
    """Write one JSON object and no other stdout text."""
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False))


def main() -> int:
    config = load_config()
    if not config or not _text(config.get("apiKey")):
        emit({"ok": False, "error": MISSING_KEY_ERROR})
        return 1

    try:
        week = fetch_usage(config, days=7)
        today = fetch_usage(config, days=1)
        emit(build_report(week, config, today_data=today))
        return 0
    except Exception as error:
        if isinstance(error, AuthenticationError):
            message = AUTH_ERROR
        elif isinstance(error, UsageError):
            message = _text(error, "获取用量数据失败")
        else:
            # Do not expose a traceback, config path, or implementation detail
            # to the long-running QML process. The fixed message is actionable
            # and keeps stdout a parseable JSON-only channel.
            message = "获取用量数据失败"
        emit({"ok": False, "error": message})
        return 1


if __name__ == "__main__":
    sys.exit(main())
