// System-locale strings for the Vibe Usage Omarchy widget.
//
// The QML entry points choose the locale from Qt.locale().name. Keeping the
// tables and formatter pure also makes the language contract testable from
// Node without requiring a running Quickshell instance.

var en = {
  brand: "Vibe Usage",
  "period.today": "Today",
  "period.24h": "24H",
  "period.7d": "7D",
  "period.30d": "30D",
  "period.meta.today": "Today",
  "period.meta.24h": "24 hours",
  "period.meta.7d": "7 days",
  "period.meta.30d": "30 days",
  "card.cost": "COST",
  "card.tokens": "TOKENS",
  "card.cache": "CACHE",
  "card.active": "ACTIVE",
  "section.trend": "TREND",
  "section.tool": "BY TOOL",
  "section.model": "BY MODEL",
  "section.host": "BY HOST",
  "action.refresh": "Refresh usage",
  "action.dashboard": "Open dashboard",
  "error.stalePrefix": "Refresh failed; showing the previous report. ",
  "error.rangeMismatch": "The helper returned a different usage range.",
  "error.missingApiKey": "Vibe Usage is not configured. Run `vibe-usage init` to configure your API key, then refresh.",
  "error.authentication": "The API key was rejected. Run `vibe-usage init` to configure it again.",
  "error.invalidRange": "Unsupported usage range.",
  "error.invalidApiUrl": "The configured API address is invalid.",
  "error.http": "The usage service returned an HTTP error.",
  "error.network": "Could not reach the usage service.",
  "error.invalidJson": "The usage service returned invalid JSON.",
  "error.invalidResponse": "The usage service returned an unsupported report.",
  "error.generic": "Unable to load Vibe Usage.",
  "empty.noUsage": "No usage recorded in this period.",
  "empty.noTrend": "No trend data.",
  "init.title": "Vibe Usage isn't configured",
  "init.instructions": "Run `vibe-usage init` to configure your API key, then refresh.",
  "empty.noReport": "No Vibe Usage report available.",
  "loading.collecting": "Collecting Vibe Usage…",
  "status.loading": "Loading",
  "status.unavailable": "Unavailable",
  "status.stale": "stale",
  "status.refreshing": "refreshing…",
  "status.updatedUnavailable": "updated time unavailable",
  "status.updatedJustNow": "updated just now",
  "status.updatedMinutes": "updated {minutes}m ago",
  "status.updatedHours": "updated {hours}h ago",
  "status.updatedDays": "updated {days}d ago",
  "tooltip.unavailable": "Vibe Usage unavailable",
  "tooltip.loading": "Vibe Usage · loading",
  "tooltip.tokens": "tokens",
  "meta.summary": "{sessions} sessions · {active} active",
};

var zhCN = {
  brand: "Vibe Usage",
  "period.today": "今天",
  "period.24h": "24小时",
  "period.7d": "7天",
  "period.30d": "30天",
  "period.meta.today": "今天",
  "period.meta.24h": "24小时",
  "period.meta.7d": "7天",
  "period.meta.30d": "30天",
  "card.cost": "费用",
  "card.tokens": "Token",
  "card.cache": "缓存",
  "card.active": "活跃",
  "section.trend": "趋势",
  "section.tool": "按工具",
  "section.model": "按模型",
  "section.host": "按主机",
  "action.refresh": "刷新用量",
  "action.dashboard": "打开仪表盘",
  "error.stalePrefix": "刷新失败，显示上一次报告。",
  "error.rangeMismatch": "辅助程序返回了不同的用量范围。",
  "error.missingApiKey": "Vibe Usage 尚未配置。运行 `vibe-usage init` 配置 API 密钥，然后刷新。",
  "error.authentication": "API Key 被拒绝。请运行 `vibe-usage init` 重新配置。",
  "error.invalidRange": "不支持的用量范围。",
  "error.invalidApiUrl": "配置的 API 地址无效。",
  "error.http": "用量服务返回了 HTTP 错误。",
  "error.network": "无法连接到用量服务。",
  "error.invalidJson": "用量服务返回了无效 JSON。",
  "error.invalidResponse": "用量服务返回了不支持的报告格式。",
  "error.generic": "无法加载 Vibe Usage。",
  "empty.noUsage": "此时间段没有用量记录。",
  "empty.noTrend": "没有趋势数据。",
  "init.title": "Vibe Usage 尚未配置",
  "init.instructions": "运行 `vibe-usage init` 配置 API 密钥，然后刷新。",
  "empty.noReport": "没有可用的 Vibe Usage 报告。",
  "loading.collecting": "正在获取 Vibe Usage…",
  "status.loading": "加载中",
  "status.unavailable": "不可用",
  "status.stale": "数据已过期",
  "status.refreshing": "正在刷新…",
  "status.updatedUnavailable": "更新时间不可用",
  "status.updatedJustNow": "刚刚更新",
  "status.updatedMinutes": "{minutes} 分钟前更新",
  "status.updatedHours": "{hours} 小时前更新",
  "status.updatedDays": "{days} 天前更新",
  "tooltip.unavailable": "Vibe Usage 不可用",
  "tooltip.loading": "Vibe Usage · 加载中",
  "tooltip.tokens": "Token",
  "meta.summary": "{sessions} 个会话 · 活跃 {active}",
};

var tables = { en: en, "zh-CN": zhCN };

var ERROR_KEYS = {
  missing_api_key: "error.missingApiKey",
  authentication: "error.authentication",
  invalid_range: "error.invalidRange",
  invalid_api_url: "error.invalidApiUrl",
  http_error: "error.http",
  network_error: "error.network",
  invalid_json: "error.invalidJson",
  invalid_response: "error.invalidResponse",
  range_mismatch: "error.rangeMismatch",
  generic: "error.generic",
};

function normalizeLocale(value) {
  var name = String(value === undefined || value === null ? "" : value)
    .trim()
    .replace(/_/g, "-")
    .toLowerCase();
  return name.indexOf("zh") === 0 ? "zh-CN" : "en";
}

function interpolate(text, params) {
  if (!params || typeof params !== "object") return text;
  return text.replace(/\{([A-Za-z0-9_]+)\}/g, (match, name) => {
    var value = params[name];
    return value === undefined || value === null ? match : String(value);
  });
}

function t(key, params, locale) {
  // Accept t(key, locale) for simple callers as well as the documented
  // t(key, params, locale) form.
  var values = params;
  var localeName = locale;
  if (localeName === undefined && typeof values === "string") {
    localeName = values;
    values = null;
  }
  var selected = normalizeLocale(localeName);
  var strings = tables[selected] || tables.en;
  var text = strings[key];
  if (text === undefined) text = tables.en[key];
  if (text === undefined) text = String(key);
  return interpolate(text, values);
}

function normalizeErrorCode(value) {
  var code = String(value === undefined || value === null ? "" : value)
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
  return ERROR_KEYS[code] ? code : "generic";
}

function errorCodeFromMessage(value) {
  var text = String(value || "");
  if (
    /未配置\s*API\s*Key|missing.*api\s*key|not configured|isn't configured/i.test(
      text,
    )
  )
    return "missing_api_key";
  if (/API\s*Key\s*无效|authentication|unauthorized|rejected|\b401\b/i.test(text))
    return "authentication";
  if (/不支持的用量范围|unsupported.*range|different usage range/i.test(text))
    return "invalid_range";
  if (/配置中的 API 地址无效|invalid.*api.*(url|address)/i.test(text))
    return "invalid_api_url";
  if (/HTTP\s*\d+|http error/i.test(text)) return "http_error";
  if (/网络请求失败|network|could not reach/i.test(text)) return "network_error";
  if (/无效 JSON|invalid json/i.test(text)) return "invalid_json";
  if (/返回格式无效|unsupported report|unsupported.*format/i.test(text))
    return "invalid_response";
  return "generic";
}

function errorText(code, params, locale) {
  var selected = normalizeErrorCode(code);
  return t(ERROR_KEYS[selected], params, locale);
}

function requiresInit(code) {
  var selected = normalizeErrorCode(code);
  return selected === "missing_api_key" || selected === "authentication";
}

if (typeof module !== "undefined") {
  module.exports = {
    en: en,
    zhCN: zhCN,
    tables: tables,
    normalizeLocale: normalizeLocale,
    interpolate: interpolate,
    t: t,
    normalizeErrorCode: normalizeErrorCode,
    errorCodeFromMessage: errorCodeFromMessage,
    errorText: errorText,
    requiresInit: requiresInit,
  };
}
