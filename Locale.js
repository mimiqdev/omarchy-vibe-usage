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
  "card.tokens": "令牌",
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
  "tooltip.tokens": "令牌",
  "meta.summary": "{sessions} 个会话 · 活跃 {active}",
};

var tables = { en: en, "zh-CN": zhCN };

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

if (typeof module !== "undefined") {
  module.exports = {
    en: en,
    zhCN: zhCN,
    tables: tables,
    normalizeLocale: normalizeLocale,
    interpolate: interpolate,
    t: t,
  };
}
