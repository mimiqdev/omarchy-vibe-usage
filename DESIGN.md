# Vibe Usage Omarchy plugin

Third-party Omarchy 4 `bar-widget` that shows [vibe-usage](https://github.com/vibe-cafe/vibe-usage) spend in the top-right bar. Not an official vibe-cafe app.

## Decisions

| Item | Decision |
| --- | --- |
| Form | Third-party Omarchy 4 `bar-widget` |
| Upstream CLI | Do **not** change `@vibe-cafe/vibe-usage`. Ship our own helper |
| `akitaonrails.ai-usagebar` | Remove when landing Phase 1 (quota meter, not spend) |
| `omarchy.agents` | Keep (subscription limits ≠ spend) |
| Sync | Daemon already running. Plugin is display-only |
| Secrets | Never load the API key into QML. Helper reads `~/.vibe-usage/config.json` |

## Phase 1 (this task)

Bar pill for today's cost + tokens, click panel (overview / by model / by tool), right-click opens the dashboard, middle-click refreshes, stale-on-failure.

## Phase 2 (out of scope)

Trend chart, project/host filters, 30d/90d, empty-state onboarding, `summary --json` upstream, official vibe-cafe repo.

Do **not** add Claude/Codex quota cards. That is `omarchy.agents`.

## Layout

```
manifest.json
README.md
DESIGN.md
BarWidget.qml
Panel.qml
Model.js
helper/usage.py
test/model.test.mjs
test/helper.test.py
```

Plugin id: `cafe.vibe.usage`  
Install path for local landing: `~/.config/omarchy/plugins/cafe.vibe.usage/`  
(`omarchy plugin add` only accepts a git URL; validate forbids symlinks. Copy the tree.)

## Architecture

```
BarWidget.qml  →  Loader Panel.qml
                      →  Process ["python3", "<pluginDir>/helper/usage.py"]
                              →  read ~/.vibe-usage/config.json
                              →  GET {apiUrl}/api/usage?days=1   # hourly, for local today
                              →  GET {apiUrl}/api/usage?days=7   # daily rollup, for 7d
```

`days=7` buckets are UTC calendar days stamped at `00:00Z` and cannot be split into a local day. Today is sliced from the hourly `days=1` payload using the machine timezone. The panel period toggle does not refetch.

## Helper contract

`python3 helper/usage.py`

- Exit 0 on success, 1 on config/auth/network failure
- stdout is JSON only
- Never print the API key

Success:

```json
{
  "ok": true,
  "fetchedAt": "2026-08-19T10:40:00+08:00",
  "dashboard": "https://vibecafe.ai/usage",
  "hostname": "WorkOmarchy",
  "windows": {
    "today": { "totals": {}, "byModel": [], "bySource": [] },
    "7d":    { "totals": {}, "byModel": [], "bySource": [] }
  }
}
```

Each window:

```json
{
  "totals": {
    "cost": 117.95,
    "tokens": 43800000,
    "sessions": 43,
    "activeSeconds": 76320
  },
  "byModel": [
    { "name": "grok-4.6", "cost": 44.61, "tokens": 7700000, "pct": 38 }
  ],
  "bySource": [
    { "name": "cursor", "cost": 80.12, "tokens": 20000000, "sessions": 20, "pct": 68 }
  ]
}
```

Failure:

```json
{ "ok": false, "error": "API Key 无效，请运行 vibe-usage init" }
```

Rules:

| Item | Definition |
| --- | --- |
| `today` | Local calendar day from hourly `days=1` buckets (`bucketStart` in the machine timezone). Do not slice `days=7` daily UTC rollups. |
| `7d` | All buckets from `days=7` (UTC daily rollup, same total as CLI `summary --days 7`) |
| `tokens` | Sum of `totalTokens` (do not add cache again) |
| `cost` | Sum of `estimatedCost` |
| `sessions` | Count in window; today uses `lastMessageAt` on the local calendar day |
| `pct` | Share of that window's `cost`, rounded to int |
| Sort | Cost descending |
| Truncate | Top 8 per list; remainder becomes `Other` |
| Timeout | 15s |
| 401 | Fixed copy pointing at `vibe-usage init` |
| Missing key | Fixed copy pointing at init |
| Source labels | `pi-coding-agent` → `pi`; everything else unchanged |

API shape (already verified):

```
GET {apiUrl}/api/usage?days=7
Authorization: Bearer vbu_...

{ hasAnyData, buckets[], sessions[] }
bucket: source, model, project, hostname, bucketStart,
        inputTokens, outputTokens, cachedInputTokens, reasoningOutputTokens,
        totalTokens, estimatedCost
session: source, project, hostname, firstMessageAt, lastMessageAt,
         durationSeconds, activeSeconds, messageCount, ...
```

## Bar pill

- Horizontal: `$117.95 · 43.8M` (`showTokens=false` → `$117.95`)
- Vertical: `$118` (integer dollars)
- Loading, no cache: `…`
- Error, no cache: `!`
- Error with cache: keep last good value; panel marks stale

Formats: cost `$` + 2 decimals (integer on vertical); tokens `43.8M` / `874K` / raw.

## Panel

Match weather / `ai-usagebar`: `KeyboardPanel` + `PanelHero`.

- Hero: title `Vibe Usage`, detail = formatted cost, meta = period + sessions + active hours
- Chips: `Today` / `7 days`
- Four totals: cost, tokens, sessions, active
- `BY MODEL` and `BY TOOL` rows with cost + bar + pct
- Footer: `updated …` and `refreshing…` when in flight

| Input | Action |
| --- | --- |
| Left click pill | Toggle panel |
| Right click pill | `omarchy launch browser https://vibecafe.ai/usage` |
| Middle click pill | Refresh |
| `r` / ↻ | Refresh |
| `h`/`l` or chips | Switch Today / 7 days (no network) |
| ↗ | Open dashboard and close panel |
| Esc | Close |
| Tab | Neighbor bar panel |

Refresh: timer `refreshIntervalSec` (default 120, clamp 30–600). On open, refetch only if last success is older than the interval. On failure keep previous report.

## Manifest

```json
{
  "schemaVersion": 1,
  "id": "cafe.vibe.usage",
  "name": "Vibe Usage",
  "version": "0.1.0",
  "author": "tonyliu",
  "license": "MIT",
  "description": "vibecafe.ai token spend in the Omarchy bar.",
  "kinds": ["bar-widget"],
  "entryPoints": { "barWidget": "BarWidget.qml" },
  "barWidget": {
    "displayName": "Vibe Usage",
    "category": "AI",
    "allowMultiple": false,
    "defaultSection": "right",
    "defaults": {
      "period": "today",
      "showTokens": true,
      "refreshIntervalSec": 120,
      "hideWhenEmpty": false
    }
  }
}
```

`period` only sets the **pill** default. Panel can switch Today/7d without writing settings.

## QML

`Model.js` is pure (no QML globals), testable from Node:

- `parseReport(stdout)`
- `formatCost` / `formatTokens` / `formatActive`
- `barText(...)`
- `autoTextSafe` / `cleanText` (same injection rules as ai-usagebar)

`BarWidget.qml` owns `open/close/opened` and injects `bar` / `settings` / `anchorItem`.

`Panel.qml` owns fetch + presentation. Resolve the helper with `Qt.resolvedUrl("helper/usage.py")` → local path. Do not put the key on argv or in the environment.

UI kit: `qs.Commons`, `qs.Ui` (`BarWidget`, `WidgetButton`, `KeyboardPanel`, `PanelHero`, `PanelActionButton`, `PanelSectionHeader`, `PanelSeparator`, `BorderSurface`).

Reference implementations (read, do not copy secrets or vendor logic):

- `~/.config/omarchy/plugins/akitaonrails.ai-usagebar/omarchy/`
- `/usr/share/omarchy/shell/plugins/panels/weather/`
- `/usr/share/omarchy/shell/Ui/`

Never edit `/usr/share/omarchy/`.

## Landing on this machine

1. `omarchy plugin validate` on the plugin folder
2. `omarchy plugin remove akitaonrails.ai-usagebar --yes`
3. Copy (not symlink) into `~/.config/omarchy/plugins/cafe.vibe.usage/`
4. `omarchy plugin enable cafe.vibe.usage --section right`
5. If needed: `omarchy bar move cafe.vibe.usage --after omarchy.tray`

## Tests

- `test/helper.test.py`: fixtures for today vs 7d split, top-8+Other, 401, missing key, source rename. Live API optional, never commit the key.
- `test/model.test.mjs`: parse + format + barText + sanitization.
- `omarchy plugin validate <plugin-dir>`
- `git diff --check <base_commit>..HEAD`
