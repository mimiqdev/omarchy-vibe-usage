// Pure data shaping and formatting for the Vibe Usage Omarchy widget.
// Keep this module free of QML globals so it can be exercised by Node tests.

var RANGES = ["today", "24h", "7d", "30d"];

function cleanText(value, maxLength) {
  var text = value === undefined || value === null ? "" : String(value);
  text = text
    .replace(/[\t\r]/g, " ")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]/g, "")
    .replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, "");
  var limit = Number(maxLength) || 2048;
  if (text.length <= limit) return text;
  var end = limit - 1;
  var finalCodeUnit = text.charCodeAt(end - 1);
  if (finalCodeUnit >= 0xd800 && finalCodeUnit <= 0xdbff) end--;
  return text.slice(0, end) + "…";
}

// Text.AutoText can interpret angle brackets as markup. Every API-controlled
// label passes through this boundary before it reaches a shared UI component.
function autoTextSafe(value) {
  return cleanText(value, 1000)
    .replace(/[\n\u2028\u2029]/g, " ")
    .replace(/</g, "‹")
    .replace(/>/g, "›");
}

function finiteNumber(value, fallback) {
  var number = Number(value);
  if (Number.isFinite(number)) return number;
  if (fallback === undefined) return 0;
  return fallback;
}

function nonNegative(value) {
  return Math.max(0, finiteNumber(value, 0));
}

function integer(value) {
  return Math.max(0, Math.round(nonNegative(value)));
}

function tidyNumber(value) {
  var number = nonNegative(value);
  if (Math.abs(number - Math.round(number)) < 1e-9) return Math.round(number);
  return Math.round(number * 1e6) / 1e6;
}

function percent(value) {
  return Math.max(0, Math.min(100, Math.round(finiteNumber(value, 0))));
}

function normalizeRange(value) {
  var range = String(
    value === undefined || value === null ? "" : value,
  ).toLowerCase();
  return RANGES.includes(range) ? range : "today";
}

function isRange(value) {
  var range = String(
    value === undefined || value === null ? "" : value,
  ).toLowerCase();
  return RANGES.includes(range);
}

function normalizeTotals(raw) {
  raw = raw && typeof raw === "object" ? raw : {};
  return {
    cost: tidyNumber(raw.cost),
    tokens: integer(raw.tokens),
    cachedTokens: integer(raw.cachedTokens),
    sessions: integer(raw.sessions),
    activeSeconds: tidyNumber(raw.activeSeconds),
  };
}

function normalizeRows(raw, includeSessions) {
  var rows = Array.isArray(raw) ? raw : [];
  var result = [];
  for (var i = 0; i < rows.length && i < 64; i++) {
    var row = rows[i];
    if (!row || typeof row !== "object") continue;
    var name = cleanText(row.name, 240).trim();
    if (name === "") name = "unknown";
    var item = {
      name: name,
      cost: tidyNumber(row.cost),
      tokens: integer(row.tokens),
      pct: percent(row.pct),
    };
    if (includeSessions) item.sessions = integer(row.sessions);
    result.push(item);
  }
  return result;
}

function normalizeSeries(raw) {
  var points = Array.isArray(raw) ? raw : [];
  var result = [];
  for (var i = 0; i < points.length && i < 512; i++) {
    var point = points[i];
    if (!point || typeof point !== "object") continue;
    var key = cleanText(point.key, 120).trim();
    if (key === "") key = String(i);
    var label = autoTextSafe(point.label || key);
    result.push({
      key: key,
      label: label,
      cost: tidyNumber(point.cost),
      tokens: integer(point.tokens),
    });
  }
  return result;
}

function parseReport(stdout) {
  try {
    var parsed = JSON.parse(String(stdout || ""));
    if (!parsed || typeof parsed !== "object")
      return { ok: false, error: "The helper returned an unsupported report." };
    if (parsed.ok !== true)
      return {
        ok: false,
        error: autoTextSafe(parsed.error || "Unable to load Vibe Usage."),
      };
    if (
      !isRange(parsed.range) ||
      !parsed.totals ||
      typeof parsed.totals !== "object"
    )
      return { ok: false, error: "The helper returned an unsupported report." };

    return {
      ok: true,
      error: "",
      range: normalizeRange(parsed.range),
      fetchedAt: cleanText(parsed.fetchedAt, 80),
      dashboard: cleanText(parsed.dashboard, 300),
      hostname: autoTextSafe(parsed.hostname),
      totals: normalizeTotals(parsed.totals),
      series: normalizeSeries(parsed.series),
      byHost: normalizeRows(parsed.byHost, true),
      bySource: normalizeRows(parsed.bySource, true),
      byModel: normalizeRows(parsed.byModel, false),
    };
  } catch (error) {
    return { ok: false, error: "The helper returned invalid JSON." };
  }
}

function windowFor(report, range) {
  if (!report || report.ok !== true || !isRange(report.range)) return null;
  if (
    range !== undefined &&
    range !== null &&
    normalizeRange(range) !== report.range
  )
    return null;
  return report;
}

function formatCost(value, vertical) {
  var amount = nonNegative(value);
  if (vertical) return "$" + Math.round(amount);
  return "$" + amount.toFixed(2);
}

function formatTokens(value) {
  var tokens = integer(value);
  if (tokens >= 1000000) return (tokens / 1000000).toFixed(1) + "M";
  if (tokens >= 1000) return Math.round(tokens / 1000) + "K";
  return String(tokens);
}

function formatActive(value) {
  var seconds = nonNegative(value);
  if (seconds >= 3600) return (seconds / 3600).toFixed(1) + "h";
  if (seconds >= 60) return Math.round(seconds / 60) + "m";
  return Math.round(seconds) + "s";
}

// Keep the pure formatter usable from Node. Panel.qml uses Locale.js for its
// static strings; these mirrored lookups let Model.js format complete
// sentences without depending on QML globals or a module loader.
var MODEL_STRINGS = {
  en: {
    brand: "Vibe Usage",
    "tooltip.unavailable": "Vibe Usage unavailable",
    "tooltip.loading": "Vibe Usage · loading",
    "period.today": "Today",
    "period.24h": "24H",
    "period.7d": "7D",
    "period.30d": "30D",
    "period.meta.today": "Today",
    "period.meta.24h": "24 hours",
    "period.meta.7d": "7 days",
    "period.meta.30d": "30 days",
    "status.stale": "stale",
    "status.updatedUnavailable": "updated time unavailable",
    "status.updatedJustNow": "updated just now",
    "status.updatedMinutes": "updated {minutes}m ago",
    "status.updatedHours": "updated {hours}h ago",
    "status.updatedDays": "updated {days}d ago",
    "tooltip.tokens": "tokens",
  },
  "zh-CN": {
    brand: "Vibe Usage",
    "tooltip.unavailable": "Vibe Usage 不可用",
    "tooltip.loading": "Vibe Usage · 加载中",
    "period.today": "今天",
    "period.24h": "24小时",
    "period.7d": "7天",
    "period.30d": "30天",
    "period.meta.today": "今天",
    "period.meta.24h": "24小时",
    "period.meta.7d": "7天",
    "period.meta.30d": "30天",
    "status.stale": "数据已过期",
    "status.updatedUnavailable": "更新时间不可用",
    "status.updatedJustNow": "刚刚更新",
    "status.updatedMinutes": "{minutes} 分钟前更新",
    "status.updatedHours": "{hours} 小时前更新",
    "status.updatedDays": "{days} 天前更新",
    "tooltip.tokens": "令牌",
  },
};

function normalizeUiLocale(value) {
  var name = String(value === undefined || value === null ? "" : value)
    .trim()
    .replace(/_/g, "-")
    .toLowerCase();
  return name.indexOf("zh") === 0 ? "zh-CN" : "en";
}

function localizedText(key, params, locale) {
  var selected = normalizeUiLocale(locale);
  var text = MODEL_STRINGS[selected][key] || MODEL_STRINGS.en[key] || String(key);
  if (!params || typeof params !== "object") return text;
  return text.replace(/\{([A-Za-z0-9_]+)\}/g, function(match, name) {
    var value = params[name];
    return value === undefined || value === null ? match : String(value);
  });
}

function periodLabel(period, locale) {
  return localizedText("period." + normalizeRange(period), null, locale);
}

function periodMetaLabel(period, locale) {
  return localizedText(
    "period.meta." + normalizeRange(period),
    null,
    locale,
  );
}

function barText(report, period, showTokens, vertical, loading, error) {
  // Also accept an options object; this keeps the pure function convenient for
  // small callers while the QML call remains explicit and readable.
  if (period && typeof period === "object") {
    var options = period;
    period = options.period || options.range;
    showTokens = options.showTokens;
    vertical = options.vertical;
    loading = options.loading;
    error = options.error;
  }

  var current = windowFor(report, period);
  if (!current) {
    if (error === true || (error && typeof error === "string")) return "!";
    return loading === false ? "!" : "…";
  }

  var text = formatCost(current.totals.cost, vertical === true);
  if (vertical !== true && showTokens !== false)
    text += " · " + formatTokens(current.totals.tokens);
  return text;
}

function tooltipText(report, period, loading, error, locale) {
  var current = windowFor(report, period);
  if (!current) {
    if (error) return localizedText("tooltip.unavailable", null, locale);
    if (loading) return localizedText("tooltip.loading", null, locale);
    return localizedText("brand", null, locale);
  }
  var totals = current.totals;
  var text =
    periodMetaLabel(period, locale) +
    " · " +
    formatCost(totals.cost, false) +
    " · " +
    formatTokens(totals.tokens) +
    " " +
    localizedText("tooltip.tokens", null, locale);
  if (error) text += " · " + localizedText("status.stale", null, locale);
  return text;
}

function updatedText(fetchedAt, nowMs, locale) {
  if (!fetchedAt)
    return localizedText("status.updatedUnavailable", null, locale);
  var fetched = new Date(String(fetchedAt)).getTime();
  if (!Number.isFinite(fetched))
    return localizedText("status.updatedUnavailable", null, locale);
  var now = Number(nowMs);
  if (!Number.isFinite(now)) now = Date.now();
  var elapsed = Math.max(0, now - fetched);
  if (elapsed < 60000)
    return localizedText("status.updatedJustNow", null, locale);
  var minutes = Math.floor(elapsed / 60000);
  if (minutes < 60)
    return localizedText("status.updatedMinutes", { minutes: minutes }, locale);
  var hours = Math.floor(minutes / 60);
  if (hours < 24)
    return localizedText("status.updatedHours", { hours: hours }, locale);
  return localizedText(
    "status.updatedDays",
    { days: Math.floor(hours / 24) },
    locale,
  );
}

function maxSeriesCost(series) {
  var points = Array.isArray(series) ? series : [];
  var maximum = 0;
  for (var i = 0; i < points.length; i++)
    maximum = Math.max(maximum, nonNegative(points[i] && points[i].cost));
  return maximum;
}

function safeDashboard(value) {
  var url = String(value || "").trim();
  // bar.run executes a shell command. Restrict the URL to characters that are
  // safe in an unquoted argument rather than allowing API data into a shell.
  if (!/^https?:\/\/[A-Za-z0-9._~:\/%+#=-]+$/i.test(url))
    return "https://vibecafe.ai/usage";
  return url;
}

function requiresInit(error) {
  var text = String(error || "");
  return /vibe-usage\s+init|未配置\s*API\s*Key|API\s*Key\s*无效/i.test(text);
}

if (typeof module !== "undefined") {
  module.exports = {
    cleanText: cleanText,
    autoTextSafe: autoTextSafe,
    parseReport: parseReport,
    normalizeRange: normalizeRange,
    windowFor: windowFor,
    formatCost: formatCost,
    formatTokens: formatTokens,
    formatActive: formatActive,
    periodLabel: periodLabel,
    periodMetaLabel: periodMetaLabel,
    barText: barText,
    tooltipText: tooltipText,
    updatedText: updatedText,
    maxSeriesCost: maxSeriesCost,
    safeDashboard: safeDashboard,
    requiresInit: requiresInit,
  };
}
