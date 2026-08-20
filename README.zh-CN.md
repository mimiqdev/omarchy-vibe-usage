# Vibe Usage Omarchy 插件

这是一个面向 Omarchy 4 的第三方 `bar-widget`，用于显示 [Vibe Usage 仪表盘](https://vibecafe.ai/usage) 平台的花费和 Token用量，并提供按本地时间查看今天、24 小时、7 天或 30 天数据的面板。账户配置和数据同步由开源的 [vibe-usage 客户端](https://github.com/vibe-cafe/vibe-usage) 提供。

[English documentation](README.md)

本插件只负责显示：`vibe-usage` daemon 继续同步本地记录，插件在刷新时发起一次只读 API 请求。本项目是独立的社区集成，与 VibeCafé 或 Omarchy 没有隶属、赞助或背书关系。

## 要求和依赖

- 带 Quickshell 插件界面的 Omarchy 4
- Python 3（只使用标准库，不需要 pip 包）
- Vibe Usage 账户，以及由 `vibe-usage init` 创建的 `~/.vibe-usage/config.json`
- 建议运行 `vibe-usage` daemon，以持续同步本地用量

辅助程序自行读取 API Key，不会通过 QML、命令行参数或环境变量传递密钥。每次请求都会带上机器的本地 IANA 时区，使日历范围与桌面时间一致。

## 安装和更新

插件 ID 是 `mimiqdev.vibe-usage`。从 GitHub 安装：

```sh
omarchy plugin add https://github.com/mimiqdev/omarchy-vibe-usage.git --enable
```

`manifest.json` 必须位于仓库根目录。通过 git 安装后，可以这样更新：

```sh
omarchy plugin update mimiqdev.vibe-usage
```

本地开发时可以用 `omarchy plugin validate` 校验当前目录。直接复制或用 `rsync` 安装的目录不是 git checkout，因此在从 git 安装之前，`omarchy plugin update mimiqdev.vibe-usage` 无法工作。

卸载本插件：

```sh
omarchy plugin remove mimiqdev.vibe-usage --yes
```

卸载小部件不会删除 `~/.vibe-usage/config.json`，也不会停止单独管理的 `vibe-usage` daemon。

如果安装了旧的配额条，只移除那个不相关的插件即可：

```sh
omarchy plugin remove akitaonrails.ai-usagebar --yes
```

不要编辑 `/usr/share/omarchy/`。

## 操作

- 左键：打开或关闭详情面板
- 右键：打开 `https://vibecafe.ai/usage`
- 中键或按 `r`：刷新当前范围
- 按 `h`/`l` 或点击范围按钮：切换今天 / 24 小时 / 7 天 / 30 天
- `费用` / `Token`：切换面板指标，不重新获取数据
- `↗`：打开仪表盘并关闭面板
- `Esc`：关闭；`Tab`：移动到相邻的条形面板

每个范围都有独立的内存报告缓存。第一次访问某个范围时才会获取数据；切换到仍在有效期内的缓存范围会立即显示，过期报告则会在后台刷新期间继续显示。手动刷新只影响当前选中的范围。刷新失败时，会保留该范围上一次成功的报告并标记为过期。没有缓存报告时，加载状态显示 `…`，错误状态显示 `!`。缺少配置或 API Key 被拒绝时，会提示运行 `vibe-usage init`。

面板会自动跟随桌面语言。名称以 `zh` 开头的语言使用简体中文，其他语言使用英文。不提供手动语言切换。

## 辅助程序接口

```sh
python3 helper/usage.py --range today|24h|7d|30d
```

每次调用只发起一个请求：

- `today`：`from=<本地零点对应的 UTC ISO 时间>&tz=<IANA 时区>`
- `24h`：`days=1&tz=<IANA 时区>`
- `7d`：`days=7&tz=<IANA 时区>`
- `30d`：`days=30&tz=<IANA 时区>`

成功的 JSON 包含 `totals`（费用、计算后的 Token 数、仅缓存 Token 数、会话数、活跃时间）、按时间排序的 `series`，以及独立排序的费用列表（`byHost`、`bySource`、`byModel`）和 Token 列表（`byHostTokens`、`bySourceTokens`、`byModelTokens`）。Token 总数与官网/Mac App 保持一致，计算公式是：

```text
inputTokens + outputTokens + reasoningOutputTokens + cachedInputTokens
```

当所有组成字段都存在时，不会再把 `totalTokens` 加到这个结果上。如果缺少任意组成字段，辅助程序会回退到 `totalTokens + cachedInputTokens`，避免显示的用量变成零。`cachedTokens` 仍然只统计 `cachedInputTokens`。来源名称会把 `pi-coding-agent` 显示为 `pi`；来自 API 的标签在显示前会经过安全处理。

失败响应会包含稳定的 `code`，例如 `authentication`、`network_error` 或 `invalid_json`。界面会按照当前桌面语言翻译这个 code，而不会直接显示辅助程序的原始错误文本。

## 面板

面板遵循官方 Mac 弹窗的顺序，而不是照搬像素布局。今天、24 小时、7 天和 30 天分别缓存报告，使用 `refreshIntervalSec` 作为有效期；不会用一个服务器范围近似另一个范围：

```text
Vibe Usage                         [刷新] [仪表盘]
[今天] [24小时] [7天] [30天]
[费用] [Token]
┌ 费用 ┐ ┌ Token ┐ ┌ 缓存 ┐ ┌ 活跃 ┐
趋势    （今天/24小时按小时，7天/30天按天）
按工具
按模型
按主机
更新时间 …
```

四张卡片始终显示费用、计算后的 Token 数、缓存 Token 数和活跃时间。`费用` / `Token` 切换会立即改变主指标、趋势条、分组行数值、百分比、进度条、排序以及独立的前八项 + `Other` 列表，不会重新请求数据。Token 数使用紧凑的 `K`、`M`、`B` 单位，最多保留一位小数。条形区和 `showTokens` 设置保持不变。每个范围的刷新使用一个辅助进程；切换标签不会取消或错误归属进行中的请求，请求失败也不会丢弃上一次成功的报告。

## 发布和版本流程

1. 保持 `manifest.json` 位于仓库根目录，并使用第三方插件 ID `mimiqdev.vibe-usage`。
2. 运行本地测试和 `omarchy plugin validate .`。
3. 将仓库提交并推送到公开 git 托管服务；tag 或 GitHub Release 可选。
4. 用户使用 `omarchy plugin add https://github.com/mimiqdev/omarchy-vibe-usage.git --enable` 安装，之后使用 `omarchy plugin update mimiqdev.vibe-usage` 更新。
5. 如有需要，可按照 [omarchyplugins.com](https://omarchyplugins.com/) 当前的说明提交公开仓库链接。这是可选的社区列表，不是 Omarchy 官方商店。

不要发布 API Key 或 `~/.vibe-usage/config.json`。本地复制适合开发，但不能提供基于 git 的更新。

## 项目结构

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
RangeCache.js
helper/usage.py
test/model.test.mjs
test/locale.test.mjs
test/range-cache.test.mjs
test/helper.test.py
```

## 测试

```sh
python3 test/helper.test.py
node test/model.test.mjs
node test/locale.test.mjs
node test/range-cache.test.mjs
omarchy plugin validate .
git diff --check
```

测试使用本地 fixture 和模拟 HTTP 响应，不需要 API Key，也不会提交密钥。
