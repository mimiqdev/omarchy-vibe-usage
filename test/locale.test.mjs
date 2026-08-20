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

assert.equal(Model.periodLabel("24h", "zh-CN"), "24小时");
assert.equal(Model.periodMetaLabel("7d", "zh-CN"), "7天");
assert.equal(
  Model.updatedText("2026-08-20T10:00:00+08:00", Date.parse("2026-08-20T10:03:00+08:00"), "zh-CN"),
  "3 分钟前更新",
);

console.log("locale tests passed");
