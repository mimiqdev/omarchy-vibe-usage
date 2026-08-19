import assert from "node:assert/strict";
import { createRequire } from "node:module";

const Model = createRequire(import.meta.url)("../Model.js");

const report = Model.parseReport(JSON.stringify({
  ok: true,
  fetchedAt: "2026-08-19T10:40:00+08:00",
  dashboard: "https://vibecafe.ai/usage",
  hostname: "Work<Omarchy>",
  windows: {
    today: {
      totals: { cost: 117.95, tokens: 43800000, sessions: 43, activeSeconds: 76320 },
      byModel: [{ name: "grok-4.6", cost: 44.61, tokens: 7700000, pct: 38 }],
      bySource: [{ name: "pi-coding-agent", cost: 80.12, tokens: 20000000, sessions: 20, pct: 68 }],
    },
    "7d": {
      totals: { cost: 200, tokens: 900000, sessions: 70, activeSeconds: 3600 },
      byModel: [],
      bySource: [],
    },
  },
}));

assert.equal(report.ok, true);
assert.equal(report.hostname, "Work‹Omarchy›");
assert.equal(Model.formatCost(117.95), "$117.95");
assert.equal(Model.formatCost(117.95, true), "$118");
assert.equal(Model.formatTokens(43800000), "43.8M");
assert.equal(Model.formatTokens(874000), "874K");
assert.equal(Model.formatTokens(874), "874");
assert.equal(Model.formatActive(76320), "21.2h");
assert.equal(Model.formatActive(90), "2m");
assert.equal(Model.formatActive(4), "4s");
assert.equal(Model.periodLabel("7d"), "7 days");
assert.equal(Model.barText(report, "today", true, false, false, ""), "$117.95 · 43.8M");
assert.equal(Model.barText(report, "today", false, false, false, ""), "$117.95");
assert.equal(Model.barText(report, "today", true, true, false, ""), "$118");
assert.equal(Model.barText(null, "today", true, false, true, ""), "…");
assert.equal(Model.barText(null, "today", true, false, false, "network down"), "!");
assert.equal(Model.tooltipText(report, "today", false, ""), "Today · $117.95 · 43.8M tokens");

const unsafe = Model.autoTextSafe("<img src='x'>\u0001\nnext");
assert.equal(unsafe, "‹img src='x'› next");
assert.equal(Model.cleanText("a\tb\r\nc"), "a b \nc");
assert.equal(Model.safeDashboard("https://vibecafe.ai/usage"), "https://vibecafe.ai/usage");
assert.equal(Model.safeDashboard("https://example.test/a; echo leaked"), "https://vibecafe.ai/usage");

assert.deepEqual(Model.parseReport(JSON.stringify({ ok: false, error: "API Key 无效" })), {
  ok: false,
  error: "API Key 无效",
});
assert.equal(Model.parseReport("not json").ok, false);
assert.equal(Model.windowFor(report, "7d").totals.sessions, 70);

console.log("model tests passed");
