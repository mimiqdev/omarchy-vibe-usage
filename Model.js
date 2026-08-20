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

function normalizeMetric(value) {
  return String(value === undefined || value === null ? "" : value).toLowerCase() ===
    "tokens"
    ? "tokens"
    : "cost";
}

function metricValue(row, metric) {
  var item = row && typeof row === "object" ? row : {};
  return normalizeMetric(metric) === "tokens" ? item.tokens : item.cost;
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

function parseFailure(message, errorCode) {
  var result = {
    ok: false,
    error: autoTextSafe(message),
  };
  var code = cleanText(errorCode, 80).trim();
  if (code !== "") result.errorCode = code;
  return result;
}

function parseReport(stdout) {
  try {
    var parsed = JSON.parse(String(stdout || ""));
    if (!parsed || typeof parsed !== "object")
      return parseFailure(
        "The helper returned an unsupported report.",
        "invalid_response",
      );
    if (parsed.ok !== true)
      return parseFailure(
        parsed.error || "Unable to load Vibe Usage.",
        parsed.code || parsed.errorCode,
      );
    if (
      !isRange(parsed.range) ||
      !parsed.totals ||
      typeof parsed.totals !== "object"
    )
      return parseFailure(
        "The helper returned an unsupported report.",
        "invalid_response",
      );

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
      byHostTokens: normalizeRows(parsed.byHostTokens, true),
      bySourceTokens: normalizeRows(parsed.bySourceTokens, true),
      byModelTokens: normalizeRows(parsed.byModelTokens, false),
    };
  } catch (error) {
    return parseFailure("The helper returned invalid JSON.", "invalid_json");
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

function compactTokens(tokens, divisor, suffix) {
  var value = (tokens / divisor).toFixed(1).replace(/\.0$/, "");
  return value + suffix;
}

function formatTokens(value) {
  var tokens = integer(value);
  if (tokens >= 1000000000)
    return compactTokens(tokens, 1000000000, "B");
  if (tokens >= 1000000) return compactTokens(tokens, 1000000, "M");
  if (tokens >= 1000) return compactTokens(tokens, 1000, "K");
  return String(tokens);
}

function formatMetric(value, metric, vertical) {
  return normalizeMetric(metric) === "tokens"
    ? formatTokens(value)
    : formatCost(value, vertical === true);
}

function formatActive(value) {
  var seconds = nonNegative(value);
  if (seconds >= 3600) return (seconds / 3600).toFixed(1) + "h";
  if (seconds >= 60) return Math.round(seconds / 60) + "m";
  return Math.round(seconds) + "s";
}

// Locale.js is the single source of truth. Node loads it directly; QML passes
// its imported Locale namespace so the same table is used in both runtimes.
var LocaleModule = null;
if (
  typeof module !== "undefined" &&
  module.exports &&
  typeof require === "function"
) {
  LocaleModule = require("./Locale.js");
}

function localizedText(key, params, locale, localeModule) {
  var source =
    localeModule && typeof localeModule.t === "function"
      ? localeModule
      : LocaleModule;
  return source ? source.t(key, params, locale) : String(key);
}

function periodLabel(period, locale, localeModule) {
  return localizedText(
    "period." + normalizeRange(period),
    null,
    locale,
    localeModule,
  );
}

function periodMetaLabel(period, locale, localeModule) {
  return localizedText(
    "period.meta." + normalizeRange(period),
    null,
    locale,
    localeModule,
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

function tooltipText(report, period, loading, error, locale, localeModule) {
  var current = windowFor(report, period);
  if (!current) {
    if (error) return localizedText("tooltip.unavailable", null, locale, localeModule);
    if (loading) return localizedText("tooltip.loading", null, locale, localeModule);
    return localizedText("brand", null, locale, localeModule);
  }
  var totals = current.totals;
  var text =
    periodMetaLabel(period, locale, localeModule) +
    " · " +
    formatCost(totals.cost, false) +
    " · " +
    formatTokens(totals.tokens) +
    " " +
    localizedText("tooltip.tokens", null, locale, localeModule);
  if (error)
    text += " · " + localizedText("status.stale", null, locale, localeModule);
  return text;
}

function updatedText(fetchedAt, nowMs, locale, localeModule) {
  if (!fetchedAt)
    return localizedText(
      "status.updatedUnavailable",
      null,
      locale,
      localeModule,
    );
  var fetched = new Date(String(fetchedAt)).getTime();
  if (!Number.isFinite(fetched))
    return localizedText(
      "status.updatedUnavailable",
      null,
      locale,
      localeModule,
    );
  var now = Number(nowMs);
  if (!Number.isFinite(now)) now = Date.now();
  var elapsed = Math.max(0, now - fetched);
  if (elapsed < 60000)
    return localizedText(
      "status.updatedJustNow",
      null,
      locale,
      localeModule,
    );
  var minutes = Math.floor(elapsed / 60000);
  if (minutes < 60)
    return localizedText(
      "status.updatedMinutes",
      { minutes: minutes },
      locale,
      localeModule,
    );
  var hours = Math.floor(minutes / 60);
  if (hours < 24)
    return localizedText(
      "status.updatedHours",
      { hours: hours },
      locale,
      localeModule,
    );
  return localizedText(
    "status.updatedDays",
    { days: Math.floor(hours / 24) },
    locale,
    localeModule,
  );
}

function maxSeriesValue(series, metric) {
  var points = Array.isArray(series) ? series : [];
  var maximum = 0;
  for (var i = 0; i < points.length; i++)
    maximum = Math.max(maximum, nonNegative(metricValue(points[i], metric)));
  return maximum;
}

function maxSeriesCost(series) {
  return maxSeriesValue(series, "cost");
}

function safeDashboard(value) {
  var url = String(value || "").trim();
  // bar.run executes a shell command. Restrict the URL to characters that are
  // safe in an unquoted argument rather than allowing API data into a shell.
  if (!/^https?:\/\/[A-Za-z0-9._~:/%+#=-]+$/i.test(url))
    return "https://vibecafe.ai/usage";
  return url;
}

function requiresInit(error) {
  var text = String(error || "");
  return /vibe-usage\s+init|未配置\s*API\s*Key|API\s*Key\s*无效|missing_api_key|authentication|unauthorized/i.test(
    text,
  );
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
    formatMetric: formatMetric,
    formatActive: formatActive,
    normalizeMetric: normalizeMetric,
    metricValue: metricValue,
    periodLabel: periodLabel,
    periodMetaLabel: periodMetaLabel,
    barText: barText,
    tooltipText: tooltipText,
    updatedText: updatedText,
    maxSeriesValue: maxSeriesValue,
    maxSeriesCost: maxSeriesCost,
    safeDashboard: safeDashboard,
    requiresInit: requiresInit,
  };
}
