import assert from "node:assert/strict";
import { createRequire } from "node:module";

const Model = createRequire(import.meta.url)("../Model.js");

const report = Model.parseReport(
  JSON.stringify({
    ok: true,
    range: "today",
    fetchedAt: "2026-08-20T10:40:00+08:00",
    dashboard: "https://vibecafe.ai/usage",
    hostname: "Work<Omarchy>",
    totals: {
      cost: 117.95,
      tokens: 43800000,
      cachedTokens: 18000000,
      sessions: 43,
      activeSeconds: 76320,
    },
    series: [
      {
        key: "2026-08-20T09:00:00+08:00",
        label: "09:00",
        cost: 12,
        tokens: 1000000,
      },
    ],
    byHost: [
      {
        name: "Work<Omarchy>",
        cost: 80.12,
        tokens: 20000000,
        sessions: 20,
        pct: 68,
      },
    ],
    bySource: [
      {
        name: "pi-coding-agent",
        cost: 80.12,
        tokens: 20000000,
        sessions: 20,
        pct: 68,
      },
    ],
    byModel: [{ name: "grok-4.6", cost: 44.61, tokens: 7700000, pct: 38 }],
  }),
);

assert.equal(report.ok, true);
assert.equal(report.hostname, "Work‹Omarchy›");
assert.equal(report.totals.cachedTokens, 18000000);
assert.equal(report.series[0].label, "09:00");
assert.equal(report.byHost[0].name, "Work<Omarchy>");
assert.equal(Model.formatCost(117.95), "$117.95");
assert.equal(Model.formatCost(117.95, true), "$118");
assert.equal(Model.formatTokens(43800000), "43.8M");
assert.equal(Model.formatTokens(874000), "874K");
assert.equal(Model.formatTokens(874), "874");
assert.equal(Model.formatActive(76320), "21.2h");
assert.equal(Model.formatActive(90), "2m");
assert.equal(Model.formatActive(4), "4s");
assert.equal(Model.periodLabel("today"), "Today");
assert.equal(Model.periodLabel("24h"), "24H");
assert.equal(Model.periodLabel("7d"), "7D");
assert.equal(Model.periodLabel("30d"), "30D");
assert.equal(
  Model.barText(report, "today", true, false, false, ""),
  "$117.95 · 43.8M",
);
assert.equal(
  Model.barText(report, "today", false, false, false, ""),
  "$117.95",
);
assert.equal(Model.barText(report, "today", true, true, false, ""), "$118");
assert.equal(Model.barText(report, "7d", true, false, false, ""), "!");
assert.equal(Model.barText(null, "today", true, false, true, ""), "…");
assert.equal(
  Model.barText(null, "today", true, false, false, "network down"),
  "!",
);
assert.equal(
  Model.tooltipText(report, "today", false, ""),
  "Today · $117.95 · 43.8M tokens",
);
assert.equal(Model.maxSeriesCost(report.series), 12);

const unsafe = Model.autoTextSafe("<img src='x'>\u0001\nnext");
assert.equal(unsafe, "‹img src='x'› next");
assert.equal(Model.cleanText("a\tb\r\nc"), "a b \nc");
assert.equal(
  Model.safeDashboard("https://vibecafe.ai/usage"),
  "https://vibecafe.ai/usage",
);
assert.equal(
  Model.safeDashboard("https://example.test/a; echo leaked"),
  "https://vibecafe.ai/usage",
);
assert.equal(Model.requiresInit("API Key 无效，请运行 vibe-usage init"), true);

assert.deepEqual(
  Model.parseReport(JSON.stringify({ ok: false, error: "API Key 无效" })),
  {
    ok: false,
    error: "API Key 无效",
  },
);
assert.equal(Model.parseReport("not json").ok, false);
assert.equal(Model.windowFor(report, "today").totals.sessions, 43);
assert.equal(Model.windowFor(report, "7d"), null);

console.log("model tests passed");
