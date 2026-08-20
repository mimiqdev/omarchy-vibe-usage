// Pure per-range cache state helpers shared by Panel.qml and Node tests.
// Requests and process ownership stay in QML; this module only handles the
// deterministic state/queue rules that keep navigation separate from fetches.

var RANGES = ["today", "24h", "7d", "30d"];

function normalizeRange(value) {
  var selected = String(value === undefined || value === null ? "" : value)
    .toLowerCase();
  return RANGES.includes(selected) ? selected : "today";
}

function rangeNames() {
  return RANGES.slice();
}

function emptyState() {
  return {
    report: null,
    loading: false,
    errorCode: "",
    initRequired: false,
    lastSuccessfulMs: 0,
  };
}

function initialStates() {
  var states = {};
  for (var i = 0; i < RANGES.length; i++) states[RANGES[i]] = emptyState();
  return states;
}

function copyState(state) {
  var source = state || {};
  return {
    report: source.report || null,
    loading: source.loading === true,
    errorCode: String(source.errorCode || ""),
    initRequired: source.initRequired === true,
    lastSuccessfulMs: Number(source.lastSuccessfulMs) || 0,
  };
}

function stateFor(states, value) {
  var selected = normalizeRange(value);
  return states && states[selected] ? states[selected] : null;
}

function updateStates(states, value, changes) {
  var selected = normalizeRange(value);
  var next = {};
  var source = states || {};
  for (var i = 0; i < RANGES.length; i++) {
    var name = RANGES[i];
    var state = copyState(source[name]);
    if (name === selected && changes) {
      if (changes.report !== undefined) state.report = changes.report;
      if (changes.loading !== undefined) state.loading = changes.loading === true;
      if (changes.errorCode !== undefined)
        state.errorCode = String(changes.errorCode || "");
      if (changes.initRequired !== undefined)
        state.initRequired = changes.initRequired === true;
      if (changes.lastSuccessfulMs !== undefined)
        state.lastSuccessfulMs = Number(changes.lastSuccessfulMs) || 0;
    }
    next[name] = state;
  }
  return next;
}

function isFresh(states, value, nowMs, ttlMs) {
  var selected = normalizeRange(value);
  var state = stateFor(states, selected);
  if (!state || !state.report || state.report.ok !== true
      || state.report.range !== selected || state.lastSuccessfulMs <= 0)
    return false;
  return Number(nowMs) - state.lastSuccessfulMs < Number(ttlMs);
}

function needsRequest(states, value, force, nowMs, ttlMs) {
  var state = stateFor(states, value);
  if (state && state.loading === true) return false;
  return force === true || !isFresh(states, value, nowMs, ttlMs);
}

function enqueue(pendingRanges, pendingForce, value, force, priority) {
  var selected = normalizeRange(value);
  var ranges = Array.isArray(pendingRanges) ? pendingRanges.slice() : [];
  var forceMap = {};
  var sourceForce = pendingForce || {};
  for (var key in sourceForce) {
    if (sourceForce[key] === true) forceMap[key] = true;
  }

  var index = ranges.indexOf(selected);
  if (index < 0) {
    if (priority === true) ranges.unshift(selected);
    else ranges.push(selected);
  } else if (priority === true && index > 0) {
    ranges.splice(index, 1);
    ranges.unshift(selected);
  }
  if (force === true) forceMap[selected] = true;
  return { ranges: ranges, force: forceMap };
}

if (typeof module !== "undefined") {
  module.exports = {
    RANGES: RANGES,
    normalizeRange: normalizeRange,
    rangeNames: rangeNames,
    emptyState: emptyState,
    initialStates: initialStates,
    copyState: copyState,
    stateFor: stateFor,
    updateStates: updateStates,
    isFresh: isFresh,
    needsRequest: needsRequest,
    enqueue: enqueue,
  };
}
