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

## Phase 1 (shipped)

Bar pill for today's cost + tokens, click panel (overview / by model / by tool), right-click opens the dashboard, middle-click refreshes, stale-on-failure.

Phase 2 adds local-time range selection, cache and active-time cards, trend bars, and host grouping.

## Phase 2 (shipped)

Follow the official Mac popover **order**, not its pixels. One API request per selected range, always with `tz=`.

```
Hero: Vibe Usage          [↻] [↗]
[Today] [24H] [7D] [30D]
┌ cost ┐ ┌ tokens ┐ ┌ cache ┐ ┌ active ┐
TREND   (simple cost bars: hours for Today/24H, days for 7D/30D)
BY HOST
BY TOOL
BY MODEL
updated …
```

### In scope

- Send `tz=<local IANA id>` on every request (this is how the Mac app gets local calendar days).
- Ranges: `today` (`from=` local midnight), `24h` (`days=1`), `7d`, `30d`. Changing range refetches once.
- Four cards: cost, tokens, **cache tokens**, active time.
- Simple unstacked cost bars. Highlight the last bar (now / today).
- `BY HOST` rows, same shape as tool/model.
- Unconfigured / 401 empty state: tell the user to run `vibe-usage init`.
- Restart the helper process cleanly on every refresh so middle-click cannot stick.

### Out of Phase 2 (Phase 3)

Donut charts, host/tool/model dropdown filters, stacked input/output/cache bars, Token/费用/活跃 chart toggle, 90D, custom date range, project filter, in-panel login, CLI `summary --json`, quota cards (`omarchy.agents`).

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

Plugin id: `mimiqdev.vibe-usage`  
Install path for local landing: `~/.config/omarchy/plugins/mimiqdev.vibe-usage/`  
(`omarchy plugin add` only accepts a git URL; validate forbids symlinks. Copy the tree.)

## Architecture

```
BarWidget.qml  →  Loader Panel.qml
                      →  Process ["python3", helper, "--range", range]
                              →  read ~/.vibe-usage/config.json
                              →  GET {apiUrl}/api/usage?<query>&tz=<local>
```

One request per refresh. `tz` is the machine IANA timezone (Mac app does this). Without it, `days=N` is UTC days and "today" is wrong.

| Range | Query |
| --- | --- |
| `today` | `from=<local midnight as UTC ISO>` + `tz=` |
| `24h` | `days=1` + `tz=` |
| `7d` / `30d` | `days=7` or `days=30` + `tz=` |

Changing the range starts a new helper process. Host / tool / model lists are built from that response only.

## Helper contract

`python3 helper/usage.py --range today|24h|7d|30d` (default `today`)

- Exit 0 on success, 1 on config/auth/network failure
- stdout is JSON only
- Never print the API key

Success:

```json
{
  "ok": true,
  "range": "today",
  "fetchedAt": "2026-08-20T10:40:00+08:00",
  "dashboard": "https://vibecafe.ai/usage",
  "hostname": "WorkOmarchy",
  "totals": {
    "cost": 206.2,
    "tokens": 22160311,
    "cachedTokens": 18000000,
    "sessions": 25,
    "activeSeconds": 170517
  },
  "series": [
    { "key": "2026-08-20T01:00:00+08:00", "label": "01:00", "cost": 12.4, "tokens": 800000 }
  ],
  "byHost": [{ "name": "Tonys-MacBook-Air", "cost": 180.1, "tokens": 20000000, "sessions": 20, "pct": 87 }],
  "bySource": [{ "name": "codex", "cost": 203.22, "tokens": 18000000, "sessions": 21, "pct": 98 }],
  "byModel": [{ "name": "gpt-5.6-sol", "cost": 126.97, "tokens": 4300000, "pct": 62 }]
}
```

Failure:

```json
{ "ok": false, "error": "API Key 无效，请运行 vibe-usage init" }
```

Rules:

| Item | Definition |
| --- | --- |
| `today` | `from=` local midnight + `tz=`. Hourly buckets. |
| `24h` | `days=1` + `tz=`. Rolling 24 hourly buckets. |
| `7d` / `30d` | `days=N` + `tz=`. Local calendar days (bucketStart is local midnight as UTC). |
| `tokens` | Sum of `totalTokens` (do not add cache again) |
| `cachedTokens` | Sum of `cachedInputTokens` |
| `cost` | Sum of `estimatedCost` |
| `sessions` | Session count in the fetched payload |
| `pct` | Share of that window's `cost`, rounded to int |
| Sort | Cost descending |
| Truncate | Top 8 per list; remainder becomes `Other` |
| Timeout | 15s |
| 401 | Fixed copy pointing at `vibe-usage init` |
| Missing key | Fixed copy pointing at init |
| Source labels | `pi-coding-agent` → `pi`; everything else unchanged |

API shape (already verified):

```
GET {apiUrl}/api/usage?<range query>&tz=<local IANA id>
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

Same Omarchy kit (`KeyboardPanel` + `PanelHero`). Arrangement follows the Mac popover, simplified.

- Hero: title `Vibe Usage`, detail = cost, meta = range + sessions + active
- Range buttons: `Today` / `24H` / `7D` / `30D` (refetch)
- Four cards: cost, tokens, cache, active
- `TREND`: one bar per series point, height by cost, last bar emphasized
- `BY HOST`, `BY TOOL`, `BY MODEL` rows (cost + bar + pct)
- Footer: `updated …` / `refreshing…`
- Missing key / 401: keep the hero, replace the body with init instructions

| Input | Action |
| --- | --- |
| Left click pill | Toggle panel |
| Right click pill | `omarchy launch browser https://vibecafe.ai/usage` |
| Middle click pill | Refresh current range |
| `r` / ↻ | Refresh |
| `h`/`l` or range buttons | Change range and refetch |
| ↗ | Open dashboard and close panel |
| Esc | Close |
| Tab | Neighbor bar panel |

Refresh: timer `refreshIntervalSec` (default 120, clamp 30–600). On open, refetch if last success is older than the interval. On failure keep the previous report. Always stop then start the helper process.

## Manifest

```json
{
  "schemaVersion": 1,
  "id": "mimiqdev.vibe-usage",
  "name": "Vibe Usage",
  "version": "0.1.0",
  "author": "mimiqdev",
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

`period` only sets the **pill** default. The panel can switch Today/24H/7D/30D without writing settings.

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
3. Copy (not symlink) into `~/.config/omarchy/plugins/mimiqdev.vibe-usage/`
4. `omarchy plugin enable mimiqdev.vibe-usage --section right`
5. If needed: `omarchy bar move mimiqdev.vibe-usage --after omarchy.tray`

## Tests

- `test/helper.test.py`: range queries with timezone, totals/cache/series, top-8+Other, 401, missing key, source rename. Live API optional, never commit the key.
- `test/model.test.mjs`: parse + format + barText + sanitization.
- `omarchy plugin validate <plugin-dir>`
- `git diff --check <base_commit>..HEAD`
