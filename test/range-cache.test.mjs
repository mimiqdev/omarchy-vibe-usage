import assert from "node:assert/strict";
import { createRequire } from "node:module";

const Cache = createRequire(import.meta.url)("../RangeCache.js");
const now = 1_000_000;
const ttl = 120_000;
const report = (range) => ({ ok: true, range, totals: {} });

let states = Cache.initialStates();
assert.equal(Cache.needsRequest(states, "today", false, now, ttl), true);

states = Cache.updateStates(states, "today", { loading: true });
assert.equal(Cache.needsRequest(states, "today", false, now, ttl), false);
assert.deepEqual(Cache.stateFor(states, "24h"), Cache.emptyState());

states = Cache.updateStates(states, "today", {
  report: report("today"),
  loading: false,
  lastSuccessfulMs: now,
});
assert.equal(Cache.isFresh(states, "today", now + ttl - 1, ttl), true);
assert.equal(Cache.needsRequest(states, "today", false, now + ttl - 1, ttl), false);
assert.equal(Cache.needsRequest(states, "today", true, now + 1, ttl), true);

// A cached range switches without a request, while a different range gets
// its own loading state and does not disturb the cached report.
states = Cache.updateStates(states, "7d", { loading: true });
assert.equal(Cache.stateFor(states, "today").report.range, "today");
assert.equal(Cache.stateFor(states, "7d").loading, true);
assert.equal(Cache.stateFor(states, "24h").loading, false);

// An old report remains available while its range refreshes in the background.
states = Cache.updateStates(states, "today", {
  loading: false,
  lastSuccessfulMs: now - ttl - 1,
});
assert.equal(Cache.needsRequest(states, "today", false, now, ttl), true);
states = Cache.updateStates(states, "today", { loading: true });
assert.equal(Cache.needsRequest(states, "today", false, now, ttl), false);
assert.equal(Cache.stateFor(states, "today").report.range, "today");

// A response is stored under its requested range, even if another tab is
// currently selected. A failed refresh keeps that range's report.
states = Cache.updateStates(states, "7d", {
  report: report("7d"),
  loading: false,
  lastSuccessfulMs: now,
});
states = Cache.updateStates(states, "24h", { loading: true });
const sevenDayReport = Cache.stateFor(states, "7d").report;
states = Cache.updateStates(states, "7d", { loading: true });
states = Cache.updateStates(states, "7d", {
  loading: false,
  errorCode: "network_error",
});
assert.equal(Cache.stateFor(states, "7d").report, sevenDayReport);
assert.equal(Cache.stateFor(states, "7d").errorCode, "network_error");
assert.equal(Cache.stateFor(states, "24h").loading, true);

// Queueing is idempotent, and a newly selected range can move ahead of
// background work without creating a second entry.
let pending = Cache.enqueue([], {}, "7d", false, false);
pending = Cache.enqueue(pending.ranges, pending.force, "30d", false, false);
pending = Cache.enqueue(pending.ranges, pending.force, "7d", false, true);
assert.deepEqual(pending.ranges, ["7d", "30d"]);
pending = Cache.enqueue(pending.ranges, pending.force, "7d", true, true);
assert.equal(pending.force["7d"], true);
assert.deepEqual(pending.ranges, ["7d", "30d"]);

console.log("range cache tests passed");
