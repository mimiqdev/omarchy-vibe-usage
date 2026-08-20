#!/usr/bin/env python3
"""Fetch and shape one Vibe Usage API window for the Omarchy widget.

The helper is intentionally a small, dependency-free process. It reads the
credential from vibe-usage's owner-only config file, performs one authenticated
request for the selected range, and writes exactly one JSON document to
stdout. QML never sees the API key.
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
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API_TIMEOUT_SECONDS = 15
DEFAULT_API_URL = "https://vibecafe.ai"
AUTH_ERROR = "API Key 无效，请运行 vibe-usage init"
MISSING_KEY_ERROR = "未配置 API Key，请运行 vibe-usage init"
RANGE_ERROR = "不支持的用量范围，请使用 today、24h、7d 或 30d"
RANGES = ("today", "24h", "7d", "30d")

ERROR_AUTHENTICATION = "authentication"
ERROR_MISSING_API_KEY = "missing_api_key"
ERROR_INVALID_RANGE = "invalid_range"
ERROR_INVALID_API_URL = "invalid_api_url"
ERROR_HTTP = "http_error"
ERROR_NETWORK = "network_error"
ERROR_INVALID_JSON = "invalid_json"
ERROR_INVALID_RESPONSE = "invalid_response"
ERROR_GENERIC = "generic"


class UsageError(Exception):
    """An expected, user-facing helper failure."""

    def __init__(self, message: str, code: str = ERROR_GENERIC):
        super().__init__(message)
        self.code = code


class AuthenticationError(UsageError):
    """The API rejected the configured key."""

    def __init__(self, message: str = AUTH_ERROR):
        super().__init__(message, ERROR_AUTHENTICATION)


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


def normalize_range(value: Any) -> str:
    """Return a supported range name or raise a user-facing error."""
    range_name = _text(value).lower()
    if range_name not in RANGES:
        raise UsageError(RANGE_ERROR, ERROR_INVALID_RANGE)
    return range_name


def _api_url(config: Mapping[str, Any]) -> str:
    value = (_text(config.get("apiUrl")) or DEFAULT_API_URL).rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise UsageError("配置中的 API 地址无效", ERROR_INVALID_API_URL)
    return value


def dashboard_url(api_url: str) -> str:
    """Build the dashboard URL without duplicating a trailing slash."""
    return api_url.rstrip("/") + "/usage"


def _valid_zone_name(value: str) -> str | None:
    candidate = value.strip()
    if candidate.startswith(":"):
        candidate = candidate[1:]
    if candidate.startswith("/usr/share/zoneinfo/"):
        candidate = candidate[len("/usr/share/zoneinfo/") :]
    if not candidate:
        return None
    try:
        ZoneInfo(candidate)
    except (KeyError, ValueError):
        return None
    return candidate


def local_timezone_name() -> str:
    """Find the machine's IANA timezone without an extra Python dependency.

    ``VIBE_USAGE_TIMEZONE`` is a test/deployment override. Normal Linux
    installs expose the same name in ``/etc/timezone`` or in the target of
    ``/etc/localtime``. UTC is a safe final fallback and is itself an IANA
    timezone.
    """
    for variable in ("VIBE_USAGE_TIMEZONE", "TZ"):
        value = _valid_zone_name(os.environ.get(variable, ""))
        if value:
            return value

    try:
        value = _valid_zone_name(Path("/etc/timezone").read_text(encoding="utf-8"))
        if value:
            return value
    except (OSError, UnicodeError):
        value = None

    try:
        resolved = Path("/etc/localtime").resolve()
        marker = "/zoneinfo/"
        path = str(resolved)
        if marker in path:
            value = _valid_zone_name(path.split(marker, 1)[1])
            if value:
                return value
    except OSError:
        path = ""

    tzinfo = datetime.now().astimezone().tzinfo
    value = _valid_zone_name(_text(getattr(tzinfo, "key", "")))
    return value or "UTC"


def _zone(timezone_name: str | None = None) -> Any:
    name = timezone_name or local_timezone_name()
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        return timezone.utc


def _aware_now(now: datetime | None, zone: Any) -> datetime:
    current = now or datetime.now(zone)
    if current.tzinfo is None:
        return current.replace(tzinfo=zone)
    return current.astimezone(zone)


def _parse_instant(value: Any, zone: Any | None = None) -> datetime | None:
    """Parse an API instant and attach the selected zone to naive values."""
    target_zone = zone or _zone()
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
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=target_zone)
    return parsed


def local_date(value: Any, timezone_name: str | None = None) -> date | None:
    """Interpret an API instant in the selected local calendar."""
    parsed = _parse_instant(value, _zone(timezone_name))
    if parsed is None:
        return None
    return parsed.astimezone(_zone(timezone_name)).date()


def _today(now: datetime | None = None, timezone_name: str | None = None) -> date:
    zone = _zone(timezone_name)
    return _aware_now(now, zone).date()


def _timestamp(now: datetime | None = None, timezone_name: str | None = None) -> str:
    zone = _zone(timezone_name)
    return _aware_now(now, zone).isoformat(timespec="seconds")


def local_midnight_iso(
    now: datetime | None = None, timezone_name: str | None = None
) -> str:
    """Return local midnight represented as a UTC ISO instant."""
    zone = _zone(timezone_name)
    current = _aware_now(now, zone)
    midnight = datetime.combine(current.date(), datetime.min.time(), tzinfo=zone)
    return (
        midnight.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _request_url(
    api_url: str,
    range_name: str | int = "today",
    *,
    now: datetime | None = None,
    timezone_name: str | None = None,
) -> str:
    """Build the single range request, including the local IANA timezone.

    The integer form is retained for small integrations that used the Phase 1
    private helper: 1 maps to ``24h`` and 7 maps to ``7d``.
    """
    if isinstance(range_name, int) and not isinstance(range_name, bool):
        range_name = "24h" if range_name == 1 else "7d" if range_name == 7 else "30d"
    selected = normalize_range(range_name)
    zone_name = timezone_name or local_timezone_name()
    params: list[tuple[str, str | int]]
    if selected == "today":
        params = [("from", local_midnight_iso(now, zone_name)), ("tz", zone_name)]
    else:
        days = {"24h": 1, "7d": 7, "30d": 30}[selected]
        params = [("days", days), ("tz", zone_name)]
    return api_url.rstrip("/") + "/api/usage?" + urlencode(params)


def fetch_usage(
    config: Mapping[str, Any],
    opener: Callable[..., Any] | None = None,
    *,
    range_name: str = "today",
    now: datetime | None = None,
    timezone_name: str | None = None,
    days: int | None = None,
) -> Mapping[str, Any]:
    """Fetch exactly one API report for ``range_name``.

    ``opener`` is injectable for offline tests; production uses urllib with a
    15-second timeout. ``days`` is a compatibility spelling for old callers
    and still receives the new timezone query parameter.
    """
    api_key = _text(config.get("apiKey"))
    if not api_key:
        raise UsageError(MISSING_KEY_ERROR, ERROR_MISSING_API_KEY)
    api_url = _api_url(config)
    if days is not None:
        range_name = "24h" if days == 1 else "7d" if days == 7 else "30d"
    selected = normalize_range(range_name)
    zone_name = timezone_name or local_timezone_name()
    request = Request(
        _request_url(api_url, selected, now=now, timezone_name=zone_name),
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
        raise UsageError(
            f"获取用量数据失败: HTTP {error.code}", ERROR_HTTP
        ) from None
    except (URLError, TimeoutError, OSError) as error:
        message = _text(getattr(error, "reason", error), "网络请求失败")
        # urllib error text is not allowed to contain the credential. It does
        # not normally include headers, but this replacement is cheap defense
        # in depth for custom openers and future urllib changes.
        message = message.replace(api_key, "[redacted]")
        raise UsageError(
            f"获取用量数据失败: {message}", ERROR_NETWORK
        ) from None

    try:
        decoded = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
    except (UnicodeError, json.JSONDecodeError):
        raise UsageError(
            "获取用量数据失败: API 返回了无效 JSON", ERROR_INVALID_JSON
        ) from None
    if not isinstance(decoded, dict):
        raise UsageError(
            "获取用量数据失败: API 返回格式无效", ERROR_INVALID_RESPONSE
        )
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


def _tidy(value: Any) -> int | float:
    number = _non_negative(value)
    rounded = _safe_round(number)
    if abs(number - rounded) < 1e-9:
        return _safe_int(rounded)
    return _safe_round(number, 6)


def _cost(value: Any) -> float:
    return _non_negative(value)


def _tokens(value: Any) -> int | float:
    return _tidy(_non_negative(value))


def computed_total_tokens(bucket: Mapping[str, Any]) -> int | float:
    """Match the website/Mac ``computedTotal`` token definition.

    ``totalTokens`` is a billed-total field and does not include every token
    category shown by the official usage clients. The displayed token total is
    input + output + reasoning output + cached input; cached input is also
    retained separately for the cache card.
    """
    fields = (
        "inputTokens",
        "outputTokens",
        "reasoningOutputTokens",
        "cachedInputTokens",
    )
    if all(bucket.get(field) is not None for field in fields):
        return _tokens(sum(_number(bucket.get(field)) for field in fields))
    # Older or partial payloads may omit the component fields. Preserve a
    # useful displayed volume without double-counting when components exist.
    return _tokens(
        _number(bucket.get("totalTokens"))
        + _number(bucket.get("cachedInputTokens"))
    )


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


def _ensure_group(
    groups: OrderedDict[str, dict[str, int | float]],
    name: str,
    include_sessions: bool,
) -> dict[str, int | float]:
    if name not in groups:
        groups[name] = _empty_group(include_sessions)
    elif include_sessions and "sessions" not in groups[name]:
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
    ranked = sorted(
        groups.items(),
        key=lambda item: (-_number(item[1].get("cost", 0)), item[0]),
    )
    if len(ranked) > 8:
        kept = ranked[:8]
        remainder = ranked[8:]
        other = _empty_group(include_sessions)
        for _, group in remainder:
            other["cost"] = _tidy(_number(other["cost"]) + _number(group.get("cost", 0)))
            other["tokens"] = _tokens(
                _number(other["tokens"]) + _number(group.get("tokens", 0))
            )
            if include_sessions:
                other["sessions"] = _safe_int(other["sessions"]) + _safe_int(
                    group.get("sessions", 0)
                )
        kept.append(("Other", other))
    else:
        kept = ranked

    rows: list[dict[str, int | float | str]] = []
    denominator = _cost(total_cost)
    for name, group in kept:
        cost = _tidy(group.get("cost", 0))
        row: dict[str, int | float | str] = {
            "name": name,
            "cost": cost,
            "tokens": _tokens(group.get("tokens", 0)),
        }
        if include_sessions:
            row["sessions"] = _safe_int(group.get("sessions", 0))
        row["pct"] = (
            _round_percent(_number(cost) * 100 / denominator) if denominator > 0 else 0
        )
        rows.append(row)
    return rows


def _payload_lists(data: Mapping[str, Any] | None) -> tuple[list[Any], list[Any]]:
    if not isinstance(data, dict):
        raise UsageError(
            "获取用量数据失败: API 返回格式无效", ERROR_INVALID_RESPONSE
        )
    buckets = data.get("buckets")
    sessions = data.get("sessions")
    return (
        buckets if isinstance(buckets, list) else [],
        sessions if isinstance(sessions, list) else [],
    )


def _bucket_series_point(
    value: Any,
    range_name: str,
    zone: Any,
) -> tuple[str, str, Any] | None:
    """Return a stable series key, label, and chronological sort value."""
    raw = _text(value)
    parsed = _parse_instant(value, zone)
    daily = range_name in {"7d", "30d"}
    if daily:
        # Daily API rollups use the date component as the local calendar day;
        # converting a midnight UTC serialization through a positive offset
        # would incorrectly move it to the previous date.
        candidate = raw[:10]
        try:
            day = date.fromisoformat(candidate)
        except ValueError:
            if parsed is None:
                return None
            day = parsed.astimezone(zone).date()
        key = day.isoformat()
        return key, key, day

    if parsed is None:
        return None
    local = parsed.astimezone(zone)
    key = local.isoformat(timespec="seconds")
    return key, local.strftime("%H:%M"), local


def _series(
    buckets: Iterable[Any],
    range_name: str,
    zone: Any,
) -> list[dict[str, int | float | str]]:
    grouped: dict[str, dict[str, Any]] = {}
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        point = _bucket_series_point(bucket.get("bucketStart"), range_name, zone)
        if point is None:
            continue
        key, label, sort_value = point
        group = grouped.setdefault(
            key,
            {"key": key, "label": label, "sort": sort_value, "cost": 0, "tokens": 0},
        )
        group["cost"] = _tidy(_number(group["cost"]) + _cost(bucket.get("estimatedCost")))
        group["tokens"] = _tokens(
            _number(group["tokens"]) + _number(computed_total_tokens(bucket))
        )

    result: list[dict[str, int | float | str]] = []
    for group in sorted(grouped.values(), key=lambda item: item["sort"]):
        result.append(
            {
                "key": group["key"],
                "label": group["label"],
                "cost": _tidy(group["cost"]),
                "tokens": _tokens(group["tokens"]),
            }
        )
    return result


def build_window(
    buckets: Iterable[Any],
    sessions: Iterable[Any],
    *,
    range_name: str = "today",
    timezone_name: str | None = None,
) -> dict[str, Any]:
    """Aggregate one API response according to the Phase 2 contract."""
    selected = normalize_range(range_name)
    zone = _zone(timezone_name)
    bucket_values = [bucket for bucket in buckets if isinstance(bucket, dict)]
    session_values = [session for session in sessions if isinstance(session, dict)]

    total_cost = 0.0
    total_tokens: int | float = 0
    cached_tokens: int | float = 0
    by_host: OrderedDict[str, dict[str, int | float]] = OrderedDict()
    by_source: OrderedDict[str, dict[str, int | float]] = OrderedDict()
    by_model: OrderedDict[str, dict[str, int | float]] = OrderedDict()

    for bucket in bucket_values:
        cost = _cost(bucket.get("estimatedCost"))
        tokens = computed_total_tokens(bucket)
        cached = _tokens(bucket.get("cachedInputTokens"))
        total_cost += cost
        total_tokens = _tokens(_number(total_tokens) + _number(tokens))
        cached_tokens = _tokens(_number(cached_tokens) + _number(cached))

        model_group = _ensure_group(by_model, item_label(bucket.get("model")), False)
        model_group["cost"] = _tidy(_number(model_group["cost"]) + cost)
        model_group["tokens"] = _tokens(_number(model_group["tokens"]) + _number(tokens))

        source_group = _ensure_group(by_source, source_label(bucket.get("source")), True)
        source_group["cost"] = _tidy(_number(source_group["cost"]) + cost)
        source_group["tokens"] = _tokens(_number(source_group["tokens"]) + _number(tokens))

        host_group = _ensure_group(by_host, item_label(bucket.get("hostname")), True)
        host_group["cost"] = _tidy(_number(host_group["cost"]) + cost)
        host_group["tokens"] = _tokens(_number(host_group["tokens"]) + _number(tokens))

    active_seconds = 0.0
    for session in session_values:
        source_group = _ensure_group(by_source, source_label(session.get("source")), True)
        source_group["sessions"] = _safe_int(source_group["sessions"]) + 1

        host_group = _ensure_group(by_host, item_label(session.get("hostname")), True)
        host_group["sessions"] = _safe_int(host_group["sessions"]) + 1
        active_seconds += _non_negative(session.get("activeSeconds"))

    return {
        "totals": {
            "cost": _tidy(total_cost),
            "tokens": total_tokens,
            "cachedTokens": cached_tokens,
            "sessions": len(session_values),
            "activeSeconds": _tidy(active_seconds),
        },
        "series": _series(bucket_values, selected, zone),
        "byHost": _ranked(by_host, total_cost, True),
        "bySource": _ranked(by_source, total_cost, True),
        "byModel": _ranked(by_model, total_cost, False),
    }


def build_report(
    data: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
    *,
    range_name: str = "today",
    now: datetime | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    """Turn one API response into the stable JSON contract consumed by QML."""
    selected = normalize_range(range_name)
    buckets, sessions = _payload_lists(data)
    config = config or {}
    zone_name = timezone_name or local_timezone_name()
    api_url = _api_url(config)
    return {
        "ok": True,
        "range": selected,
        "fetchedAt": _timestamp(now, zone_name),
        "dashboard": dashboard_url(api_url),
        "hostname": _text(config.get("hostname")) or socket.gethostname(),
        **build_window(buckets, sessions, range_name=selected, timezone_name=zone_name),
    }


def emit(payload: Mapping[str, Any]) -> None:
    """Write one JSON object and no other stdout text."""
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False))


def main() -> int:
    requested_range = "today"
    if len(sys.argv) > 1:
        if len(sys.argv) != 3 or sys.argv[1] != "--range":
            emit({"ok": False, "code": ERROR_INVALID_RANGE, "error": RANGE_ERROR})
            return 1
        requested_range = sys.argv[2]

    try:
        selected = normalize_range(requested_range)
    except UsageError as error:
        emit({
            "ok": False,
            "code": ERROR_INVALID_RANGE,
            "error": _text(error, RANGE_ERROR),
        })
        return 1

    config = load_config()
    if not config or not _text(config.get("apiKey")):
        emit({
            "ok": False,
            "code": ERROR_MISSING_API_KEY,
            "error": MISSING_KEY_ERROR,
        })
        return 1

    try:
        data = fetch_usage(config, range_name=selected)
        emit(build_report(data, config, range_name=selected))
        return 0
    except Exception as error:
        if isinstance(error, AuthenticationError):
            code = ERROR_AUTHENTICATION
            message = AUTH_ERROR
        elif isinstance(error, UsageError):
            code = error.code
            message = _text(error, "获取用量数据失败")
        else:
            # Do not expose a traceback, config path, or implementation detail
            # to the long-running QML process. The fixed message is actionable
            # and keeps stdout a parseable JSON-only channel.
            code = ERROR_GENERIC
            message = "获取用量数据失败"
        emit({"ok": False, "code": code, "error": message})
        return 1


if __name__ == "__main__":
    sys.exit(main())
