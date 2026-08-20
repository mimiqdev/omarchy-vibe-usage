# Vibe Usage Omarchy plugin

A third-party Omarchy 4 `bar-widget` for the [Vibe Usage dashboard](https://vibecafe.ai/usage). It shows the platform's spend and token usage in the bar and provides a local-time panel for Today, 24H, 7D, or 30D. Account setup and data synchronization are provided by the open-source [vibe-usage client](https://github.com/vibe-cafe/vibe-usage).

[中文文档](README.zh-CN.md)

The plugin is display-only: the `vibe-usage` daemon keeps syncing local records, while this plugin makes one read-only API request whenever it refreshes. It is an independent community integration and is not affiliated with, sponsored by, or endorsed by VibeCafé or Omarchy.

## Requirements and dependencies

- Omarchy 4 with the Quickshell plugin UI
- Python 3 (standard library only; no pip packages)
- A Vibe Usage account and `~/.vibe-usage/config.json` created by `vibe-usage init`
- A running `vibe-usage` daemon is recommended so local usage continues to sync

The helper reads the API key itself and never passes it through QML, argv, or environment variables. Every request includes the machine's local IANA timezone so calendar ranges match the desktop.

## Install and update

The plugin id is `mimiqdev.vibe-usage`. Install it from GitHub with:

```sh
omarchy plugin add https://github.com/mimiqdev/omarchy-vibe-usage.git --enable
```

The manifest must be at the repository root. To update a git-installed copy:

```sh
omarchy plugin update mimiqdev.vibe-usage
```

For local development, `omarchy plugin validate` can validate this directory. A copied or `rsync`-installed tree is not a git checkout, so `omarchy plugin update mimiqdev.vibe-usage` will not work until the plugin is installed from git.

To uninstall this plugin:

```sh
omarchy plugin remove mimiqdev.vibe-usage --yes
```

Uninstalling the widget does not remove `~/.vibe-usage/config.json` or stop the separately managed `vibe-usage` daemon.

If the old quota meter is installed, remove only that unrelated plugin before enabling this one:

```sh
omarchy plugin remove akitaonrails.ai-usagebar --yes
```

Do not edit `/usr/share/omarchy/`.

## Controls

- Left click: open or close the detail panel
- Right click: open `https://vibecafe.ai/usage`
- Middle click or `r`: refresh the current range
- `h`/`l` or the range chips: switch Today / 24H / 7D / 30D and refetch
- `↗`: open the dashboard and close the panel
- `Esc`: close; `Tab`: move to the neighboring bar panel

A failed refresh keeps the last successful report for that range visible and marks the panel stale. With no cached report, loading displays `…` and an error displays `!`. Missing configuration or a rejected key shows instructions to run `vibe-usage init`.

The panel follows the desktop locale automatically. Locales whose name starts with `zh` use Simplified Chinese; all other locales use English. There is no manual language switch.

## Helper contract

```sh
python3 helper/usage.py --range today|24h|7d|30d
```

The helper performs one request per invocation:

- `today`: `from=<local midnight as UTC ISO>&tz=<IANA id>`
- `24h`: `days=1&tz=<IANA id>`
- `7d`: `days=7&tz=<IANA id>`
- `30d`: `days=30&tz=<IANA id>`

Successful JSON contains `totals` (cost, computed tokens, cache-only tokens, sessions, active time), chronological `series` bars, and top-eight `byHost`, `bySource`, and `byModel` lists. Token totals match the official website/Mac app:

```text
inputTokens + outputTokens + reasoningOutputTokens + cachedInputTokens
```

When all component fields are present, `totalTokens` is not added to this value. If any component field is omitted, the helper falls back to `totalTokens + cachedInputTokens` so the displayed volume is not lost. `cachedTokens` remains the sum of `cachedInputTokens` only. Source labels rename `pi-coding-agent` to `pi`; API-controlled labels are sanitized before they reach the UI.

Failure responses include a stable `code` such as `authentication`, `network_error`, or `invalid_json`. The UI translates that code for the active desktop locale instead of displaying the helper's raw error text.

## Panel

The panel follows the official Mac popover's order, not its pixels:

```text
Vibe Usage                         [refresh] [dashboard]
[Today] [24H] [7D] [30D]
┌ cost ┐ ┌ tokens ┐ ┌ cache ┐ ┌ active ┐
TREND   (hourly bars for Today/24H, daily bars for 7D/30D)
BY TOOL
BY MODEL
BY HOST
updated …
```

The four cards show cost, computed tokens, cache tokens, and active time. Breakdown rows show cost, percentage, and a bar. The helper is restarted cleanly for every refresh; a failed request never discards the previous successful report.

## Publish and release

1. Keep `manifest.json` at the repository root and use the third-party id `mimiqdev.vibe-usage`.
2. Run the local tests and `omarchy plugin validate .`.
3. Commit and push the repository to a public git host. Tags or GitHub releases are optional.
4. Users install with `omarchy plugin add https://github.com/mimiqdev/omarchy-vibe-usage.git --enable` and later update with `omarchy plugin update mimiqdev.vibe-usage`.
5. If desired, submit the public repository link to [omarchyplugins.com](https://omarchyplugins.com/) according to that site's current instructions. This is an optional community listing, not an official Omarchy store.

Do not publish API keys or `~/.vibe-usage/config.json`. A local copy is useful for development but does not provide git-based updates.

## Project layout

```text
manifest.json
README.md
README.zh-CN.md
DESIGN.md
LICENSE
BarWidget.qml
Panel.qml
Model.js
Locale.js
helper/usage.py
test/model.test.mjs
test/locale.test.mjs
test/helper.test.py
```

## Tests

```sh
python3 test/helper.test.py
node test/model.test.mjs
node test/locale.test.mjs
omarchy plugin validate .
git diff --check
```

The tests use local fixtures and mocked HTTP responses. No API key is required or committed.
