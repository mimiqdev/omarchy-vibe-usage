import assert from "node:assert/strict";
import { createRequire } from "node:module";

const loadModule = createRequire(import.meta.url);
const Locale = loadModule("../Locale.js");
const Model = loadModule("../Model.js");

assert.equal(Locale.normalizeLocale("en_US"), "en");
assert.equal(Locale.normalizeLocale("zh_CN"), "zh-CN");
assert.equal(Locale.normalizeLocale("zh-Hans"), "zh-CN");
assert.equal(Locale.normalizeLocale("ja_JP"), "en");

assert.equal(Locale.t("period.today", null, "en"), "Today");
assert.equal(Locale.t("period.today", null, "zh-CN"), "今天");
assert.equal(Locale.t("section.tool", null, "zh-CN"), "按工具");
assert.equal(Locale.t("metric.cost", null, "en"), "Cost");
assert.equal(Locale.t("metric.tokens", null, "en"), "Token");
assert.equal(Locale.t("metric.cost", null, "zh-CN"), "费用");
assert.equal(Locale.t("metric.tokens", null, "zh-CN"), "Token");
assert.equal(Locale.t("card.cost", "zh-CN"), "费用");
assert.equal(
  Locale.t(
    "meta.summary",
    { sessions: 3, active: "2.5h" },
    "en",
  ),
  "3 sessions · 2.5h active",
);
assert.equal(
  Locale.t(
    "meta.summary",
    { sessions: 3, active: "2.5h" },
    "zh-CN",
  ),
  "3 个会话 · 活跃 2.5h",
);
assert.equal(Locale.t("missing.key", null, "zh-CN"), "missing.key");
assert.deepEqual(
  Object.keys(Locale.en).sort(),
  Object.keys(Locale.zhCN).sort(),
);
assert.equal(
  Locale.errorCodeFromMessage("未配置 API Key，请运行 vibe-usage init"),
  "missing_api_key",
);
assert.equal(
  Locale.errorCodeFromMessage("获取用量数据失败: HTTP 503"),
  "http_error",
);
assert.equal(
  Locale.errorCodeFromMessage("获取用量数据失败: API 返回了无效 JSON"),
  "invalid_json",
);
assert.equal(
  Locale.errorText("network_error", null, "en"),
  "Could not reach the usage service.",
);
assert.equal(
  Locale.errorText("network_error", null, "zh-CN"),
  "无法连接到用量服务。",
);

const report = {
  ok: true,
  range: "today",
  totals: {
    cost: 1.25,
    tokens: 1000,
    cachedTokens: 100,
    sessions: 2,
    activeSeconds: 90,
  },
};
for (const locale of ["en", "zh-CN"]) {
  assert.equal(
    Model.periodLabel("today", locale),
    Locale.t("period.today", null, locale),
  );
  assert.equal(
    Model.periodMetaLabel("30d", locale),
    Locale.t("period.meta.30d", null, locale),
  );
  assert.equal(
    Model.tooltipText(report, "today", false, "", locale),
    `${Locale.t("period.meta.today", null, locale)} · $1.25 · 1K ${Locale.t("tooltip.tokens", null, locale)}`,
  );
  assert.equal(
    Model.updatedText(
      "2026-08-20T10:00:00+08:00",
      Date.parse("2026-08-20T10:03:00+08:00"),
      locale,
    ),
    Locale.t("status.updatedMinutes", { minutes: 3 }, locale),
  );
}

assert.equal(Model.periodLabel("24h", "zh-CN"), "24小时");
assert.equal(Model.periodLabel("today", "zh-CN", Locale), "今天");
assert.equal(Model.periodMetaLabel("7d", "zh-CN"), "7天");
assert.equal(
  Model.updatedText("2026-08-20T10:00:00+08:00", Date.parse("2026-08-20T10:03:00+08:00"), "zh-CN"),
  "3 分钟前更新",
);

console.log("locale tests passed");
