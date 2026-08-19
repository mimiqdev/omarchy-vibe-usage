// Pure data shaping and formatting for the Vibe Usage Omarchy widget.
// Keep this module free of QML globals so it can be exercised by Node tests.

function cleanText(value, maxLength) {
  var text = value === undefined || value === null ? "" : String(value)
  text = text.replace(/[\t\r]/g, " ")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]/g, "")
    .replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, "")
  var limit = Number(maxLength) || 2048
  if (text.length <= limit) return text
  var end = limit - 1
  var finalCodeUnit = text.charCodeAt(end - 1)
  if (finalCodeUnit >= 0xd800 && finalCodeUnit <= 0xdbff) end--
  return text.slice(0, end) + "…"
}

// Text.AutoText can interpret angle brackets as markup. Every API-controlled
// label passes through this boundary before it reaches a shared UI component.
function autoTextSafe(value) {
  return cleanText(value, 1000)
    .replace(/[\n\u2028\u2029]/g, " ")
    .replace(/</g, "‹")
    .replace(/>/g, "›")
}

function finiteNumber(value, fallback) {
  var number = Number(value)
  return isFinite(number) ? number : (fallback === undefined ? 0 : fallback)
}

function nonNegative(value) {
  return Math.max(0, finiteNumber(value, 0))
}

function integer(value) {
  return Math.max(0, Math.round(nonNegative(value)))
}

function tidyNumber(value) {
  var number = nonNegative(value)
  if (Math.abs(number - Math.round(number)) < 1e-9) return Math.round(number)
  return Math.round(number * 1e6) / 1e6
}

function percent(value) {
  return Math.max(0, Math.min(100, Math.round(finiteNumber(value, 0))))
}

function normalizeTotals(raw) {
  raw = raw && typeof raw === "object" ? raw : {}
  return {
    cost: tidyNumber(raw.cost),
    tokens: integer(raw.tokens),
    sessions: integer(raw.sessions),
    activeSeconds: tidyNumber(raw.activeSeconds)
  }
}

function normalizeRows(raw, includeSessions) {
  var rows = Array.isArray(raw) ? raw : []
  var result = []
  for (var i = 0; i < rows.length && i < 64; i++) {
    var row = rows[i]
    if (!row || typeof row !== "object") continue
    var name = cleanText(row.name, 240).trim()
    if (name === "") name = "unknown"
    var item = {
      name: name,
      cost: tidyNumber(row.cost),
      tokens: integer(row.tokens),
      pct: percent(row.pct)
    }
    if (includeSessions) item.sessions = integer(row.sessions)
    result.push(item)
  }
  return result
}

function normalizeWindow(raw) {
  raw = raw && typeof raw === "object" ? raw : {}
  return {
    totals: normalizeTotals(raw.totals),
    byModel: normalizeRows(raw.byModel, false),
    bySource: normalizeRows(raw.bySource, true)
  }
}

function parseReport(stdout) {
  try {
    var parsed = JSON.parse(String(stdout || ""))
    if (!parsed || typeof parsed !== "object")
      return { ok: false, error: "The helper returned an unsupported report." }
    if (parsed.ok !== true)
      return {
        ok: false,
        error: autoTextSafe(parsed.error || "Unable to load Vibe Usage.")
      }
    if (!parsed.windows || typeof parsed.windows !== "object")
      return { ok: false, error: "The helper returned an unsupported report." }

    return {
      ok: true,
      error: "",
      fetchedAt: cleanText(parsed.fetchedAt, 80),
      dashboard: cleanText(parsed.dashboard, 300),
      hostname: autoTextSafe(parsed.hostname),
      windows: {
        today: normalizeWindow(parsed.windows.today),
        "7d": normalizeWindow(parsed.windows["7d"])
      }
    }
  } catch (error) {
    return { ok: false, error: "The helper returned invalid JSON." }
  }
}

function windowFor(report, period) {
  if (!report || report.ok !== true || !report.windows) return null
  return period === "7d" ? report.windows["7d"] : report.windows.today
}

function formatCost(value, vertical) {
  var amount = nonNegative(value)
  if (vertical) return "$" + Math.round(amount)
  return "$" + amount.toFixed(2)
}

function formatTokens(value) {
  var tokens = integer(value)
  if (tokens >= 1000000) return (tokens / 1000000).toFixed(1) + "M"
  if (tokens >= 1000) return Math.round(tokens / 1000) + "K"
  return String(tokens)
}

function formatActive(value) {
  var seconds = nonNegative(value)
  if (seconds >= 3600) return (seconds / 3600).toFixed(1) + "h"
  if (seconds >= 60) return Math.round(seconds / 60) + "m"
  return Math.round(seconds) + "s"
}

function periodLabel(period) {
  return period === "7d" ? "7 days" : "Today"
}

function barText(report, period, showTokens, vertical, loading, error) {
  // Also accept an options object; this keeps the pure function convenient for
  // small callers while the QML call remains explicit and readable.
  if (period && typeof period === "object") {
    var options = period
    period = options.period
    showTokens = options.showTokens
    vertical = options.vertical
    loading = options.loading
    error = options.error
  }

  var hasReport = report && report.ok === true
  if (!hasReport) {
    if (error === true || (error && typeof error === "string")) return "!"
    return loading === false ? "!" : "…"
  }

  var current = windowFor(report, period)
  if (!current) return "!"
  var text = formatCost(current.totals.cost, vertical === true)
  if (vertical !== true && showTokens !== false)
    text += " · " + formatTokens(current.totals.tokens)
  return text
}

function tooltipText(report, period, loading, error) {
  if (!report || report.ok !== true) return error ? "Vibe Usage unavailable" : (loading ? "Vibe Usage · loading" : "Vibe Usage")
  var current = windowFor(report, period)
  if (!current) return "Vibe Usage"
  var totals = current.totals
  var text = periodLabel(period) + " · " + formatCost(totals.cost, false)
    + " · " + formatTokens(totals.tokens) + " tokens"
  if (error) text += " · stale"
  return text
}

function updatedText(fetchedAt, nowMs) {
  if (!fetchedAt) return "updated time unavailable"
  var fetched = new Date(String(fetchedAt)).getTime()
  if (!isFinite(fetched)) return "updated time unavailable"
  var now = Number(nowMs)
  if (!isFinite(now)) now = Date.now()
  var elapsed = Math.max(0, now - fetched)
  if (elapsed < 60000) return "updated just now"
  var minutes = Math.floor(elapsed / 60000)
  if (minutes < 60) return "updated " + minutes + "m ago"
  var hours = Math.floor(minutes / 60)
  if (hours < 24) return "updated " + hours + "h ago"
  return "updated " + Math.floor(hours / 24) + "d ago"
}

function safeDashboard(value) {
  var url = String(value || "").trim()
  // bar.run executes a shell command. Restrict the URL to characters that are
  // safe in an unquoted argument rather than allowing API data into a shell.
  if (!/^https?:\/\/[A-Za-z0-9._~:/%+#=-]+$/i.test(url))
    return "https://vibecafe.ai/usage"
  return url
}

if (typeof module !== "undefined") {
  module.exports = {
    cleanText: cleanText,
    autoTextSafe: autoTextSafe,
    parseReport: parseReport,
    windowFor: windowFor,
    formatCost: formatCost,
    formatTokens: formatTokens,
    formatActive: formatActive,
    periodLabel: periodLabel,
    barText: barText,
    tooltipText: tooltipText,
    updatedText: updatedText,
    safeDashboard: safeDashboard
  }
}
