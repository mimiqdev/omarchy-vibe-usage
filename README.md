# Vibe Usage Omarchy plugin

A third-party Omarchy 4 `bar-widget` for [vibe-usage](https://github.com/vibe-cafe/vibe-usage). It shows spend and tokens in the bar, with a local-time panel for Today, 24H, 7D, or 30D.

The plugin is display-only. The `vibe-usage` daemon continues to sync local records; the plugin makes one read-only API request when it refreshes.

## Requirements

- Omarchy 4 with the Quickshell plugin UI
- Python 3
- `~/.vibe-usage/config.json` created by `vibe-usage init`
- A running `vibe-usage` daemon (recommended)

The helper reads the API key itself and never passes it through QML, argv, or environment variables. Every request includes the machine's local IANA timezone so calendar ranges match the desktop.

## Install locally

`omarchy plugin add` accepts a git URL and the validator rejects symlinks. Copy this tree to the local plugin directory:

```sh
mkdir -p ~/.config/omarchy/plugins/mimiqdev.vibe-usage
cp -a ./. ~/.config/omarchy/plugins/mimiqdev.vibe-usage/
omarchy plugin validate ~/.config/omarchy/plugins/mimiqdev.vibe-usage
omarchy plugin enable mimiqdev.vibe-usage --section right
```

If the old quota meter is installed, remove only that plugin before enabling this one:

```sh
omarchy plugin remove akitaonrails.ai-usagebar --yes
```

The plugin id is `mimiqdev.vibe-usage`; do not edit `/usr/share/omarchy/`.

## Controls

- Left click: open or close the detail panel
- Right click: open `https://vibecafe.ai/usage`
- Middle click or `r`: refresh the current range
- `h`/`l` or the range chips: switch Today / 24H / 7D / 30D and refetch
- `↗`: open the dashboard and close the panel
- `Esc`: close; `Tab`: move to the neighboring bar panel

A failed refresh keeps the last successful report for that range visible and marks the panel stale. With no cached report, loading displays `…` and an error displays `!`. Missing configuration or a rejected key shows instructions to run `vibe-usage init`.

## Helper contract

```sh
python3 helper/usage.py --range today|24h|7d|30d
```

The helper performs one request per invocation:

- `today`: `from=<local midnight as UTC ISO>&tz=<IANA id>`
- `24h`: `days=1&tz=<IANA id>`
- `7d`: `days=7&tz=<IANA id>`
- `30d`: `days=30&tz=<IANA id>`

The successful JSON contains `totals` (cost, tokens, cached tokens, sessions, active time), chronological `series` bars, and top-eight `byHost`, `bySource`, and `byModel` lists. Token totals sum `totalTokens`; cache is reported separately from `cachedInputTokens`.

## Tests

```sh
python3 test/helper.test.py
node test/model.test.mjs
omarchy plugin validate .
git diff --check
```

The tests use local fixtures and mocked HTTP responses. No API key is required or committed.
