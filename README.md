# Vibe Usage Omarchy plugin

A third-party Omarchy 4 `bar-widget` for [vibe-usage](https://github.com/vibe-cafe/vibe-usage). It shows today's spend and tokens in the bar, with a panel for today or the last seven days split by model and tool.

This plugin is display-only. The `vibe-usage` daemon continues to sync local records; the plugin makes one read-only API request when it refreshes.

## Requirements

- Omarchy 4 with the Quickshell plugin UI
- Python 3
- `~/.vibe-usage/config.json` created by `vibe-usage init`
- A running `vibe-usage` daemon (recommended)

The helper reads the API key itself and never passes it through QML, argv, or environment variables.

## Install locally

`omarchy plugin add` accepts a git URL and the validator rejects symlinks. Copy this tree to the local plugin directory:

```sh
mkdir -p ~/.config/omarchy/plugins/cafe.vibe.usage
cp -a ./. ~/.config/omarchy/plugins/cafe.vibe.usage/
omarchy plugin validate ~/.config/omarchy/plugins/cafe.vibe.usage
omarchy plugin enable cafe.vibe.usage --section right
```

If the old quota meter is installed, remove only that plugin before enabling this one:

```sh
omarchy plugin remove akitaonrails.ai-usagebar --yes
```

The plugin id is `cafe.vibe.usage`; do not edit `/usr/share/omarchy/`.

## Controls

- Left click: open or close the detail panel
- Right click: open `https://vibecafe.ai/usage`
- Middle click or `r`: refresh
- `h`/`l` or the period chips: switch Today / 7 days without refetching
- `↗`: open the dashboard and close the panel
- `Esc`: close; `Tab`: move to the neighboring bar panel

A failed refresh keeps the last successful report visible and marks the panel stale. With no cached report, loading displays `…` and an error displays `!`.

## Tests

```sh
python3 test/helper.test.py
node test/model.test.mjs
omarchy plugin validate .
git diff --check 95c340d37b652cfe30a8272662cb63de35b747ec..HEAD
```

The tests use local fixtures and mocked HTTP responses. No API key is required or committed.
