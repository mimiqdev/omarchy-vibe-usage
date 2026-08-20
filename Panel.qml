import QtQuick
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

// The panel owns one helper process and keeps the last successful report when
// a later request fails. The bar widget remains the shell-facing identity.
Panel {
  id: root
  moduleName: "cafe.vibe.usage"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.45)
  readonly property color track: Style.selectedFillFor(foreground, Color.accent)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property bool vertical: bar ? bar.vertical : false

  property var report: null
  property string period: setting("period", "today") === "7d" ? "7d" : "today"
  property bool loading: true
  property bool refreshQueued: false
  property string commandStdout: ""
  property string commandStderr: ""
  property string loadError: ""
  property double lastSuccessfulMs: 0
  property double nowMs: Date.now()

  readonly property int refreshIntervalSec: Math.max(30, Math.min(600,
    Number(setting("refreshIntervalSec", 120)) || 120))
  readonly property bool showTokens: setting("showTokens", true) !== false
  readonly property bool hideWhenEmpty: setting("hideWhenEmpty", false) === true
  readonly property var currentWindow: Model.windowFor(report, period)
  readonly property var totals: currentWindow ? currentWindow.totals
    : ({ cost: 0, tokens: 0, sessions: 0, activeSeconds: 0 })
  readonly property bool emptyReport: currentWindow
    && totals.cost === 0 && totals.tokens === 0 && totals.sessions === 0
    && totals.activeSeconds === 0
  readonly property bool alarming: loadError !== ""
  readonly property string label: hideWhenEmpty && emptyReport ? "" : barText()

  function barText() {
    return Model.barText(report, period, showTokens, vertical, loading, loadError)
  }

  function tooltipText() {
    return Model.tooltipText(report, period, loading, loadError)
  }

  function dashboardUrl() {
    return Model.safeDashboard(report ? report.dashboard : "")
  }

  function periodTitle() {
    return Model.periodLabel(period)
  }

  function periodMeta() {
    if (!currentWindow) return loading ? "Loading" : "Unavailable"
    var meta = periodTitle() + " · " + totals.sessions + " sessions · "
      + Model.formatActive(totals.activeSeconds) + " active"
    if (loadError !== "") meta += " · stale"
    return meta
  }

  function totalLabel(index) {
    return ["COST", "TOKENS", "SESSIONS", "ACTIVE"][index] || ""
  }

  function totalValue(index) {
    if (index === 0) return Model.formatCost(totals.cost, false)
    if (index === 1) return Model.formatTokens(totals.tokens)
    if (index === 2) return String(totals.sessions)
    return Model.formatActive(totals.activeSeconds)
  }

  function setPeriod(value) {
    period = value === "7d" ? "7d" : "today"
    if (panelFlick) panelFlick.contentY = 0
  }

  function switchPeriod(delta) {
    setPeriod(delta < 0 ? "today" : "7d")
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value))
  }

  function switchPanel(direction) {
    if (bar && typeof bar.switchPanelFrom === "function")
      return bar.switchPanelFrom(barIdentity, direction)
    return false
  }

  function startRefresh() {
    if (usageProcess.running) {
      refreshQueued = true
      return
    }
    refreshQueued = false
    commandStdout = ""
    commandStderr = ""
    loading = true
    usageProcess.running = true
  }

  function finishRefresh() {
    var parsed = Model.parseReport(commandStdout)
    if (parsed.ok) {
      report = parsed
      loadError = ""
      lastSuccessfulMs = Date.now()
      nowMs = lastSuccessfulMs
    } else {
      var detail = String(parsed.error || commandStderr || "").trim()
      loadError = Model.autoTextSafe(detail || "Unable to load Vibe Usage.")
    }
    loading = false
    if (refreshQueued) Qt.callLater(startRefresh)
  }

  function refresh() {
    startRefresh()
  }

  // Qt.resolvedUrl returns a file:// URL. Process argv needs a local path
  // or python3 tries to open the literal URL and writes nothing to stdout.
  function helperPath() {
    var resolved = String(Qt.resolvedUrl("helper/usage.py"))
    if (resolved.indexOf("file://") === 0) {
      var path = resolved.slice(7)
      try { return decodeURIComponent(path) } catch (e) { return path }
    }
    return resolved
  }

  function openDashboard() {
    if (bar) bar.run("omarchy launch browser " + dashboardUrl())
    root.close()
  }

  onOpenedChanged: {
    if (opened) {
      nowMs = Date.now()
      if (panelFlick) panelFlick.contentY = 0
      if (lastSuccessfulMs === 0
          || nowMs - lastSuccessfulMs >= refreshIntervalSec * 1000)
        startRefresh()
      Qt.callLater(function() { keyCatcher.forceActiveFocus() })
    }
  }

  Timer {
    interval: root.refreshIntervalSec * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.startRefresh()
  }

  Timer {
    interval: 30000
    running: root.opened
    repeat: true
    onTriggered: root.nowMs = Date.now()
  }

  Process {
    id: usageProcess
    running: false
    command: ["python3", root.helperPath()]

    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.commandStdout = text
    }

    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.commandStderr = text
    }

    onExited: {
      // Let both collectors publish their buffers before parsing stdout.
      Qt.callLater(function() { root.finishRefresh() })
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(470))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(700))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent

      onMoveRequested: function(dx, dy) {
        if (dx !== 0) root.switchPeriod(dx)
        else if (dy !== 0)
          panelFlick.contentY = root.clamp(panelFlick.contentY + dy * Style.space(56),
            0, Math.max(0, panelFlick.contentHeight - panelFlick.height))
      }
      onActivateRequested: root.refresh()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(text) {
        if (text === "r" || text === "R") root.refresh()
      }

      Flickable {
        id: panelFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height

        Column {
          id: column
          width: panelFlick.width
          spacing: Style.space(12)

          PanelHero {
            width: parent.width
            title: "Vibe Usage"
            detail: root.currentWindow ? Model.formatCost(root.totals.cost, false) : ""
            meta: root.periodMeta()
            foreground: root.foreground
            fontFamily: root.fontFamily

            iconComponent: Component {
              Text {
                text: "󰚩"
                color: root.alarming ? root.urgent : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.display
              }
            }

            trailingControl: Component {
              Row {
                spacing: Style.space(4)

                PanelActionButton {
                  iconText: "󰑐"
                  tooltipText: "Refresh usage"
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                  enabled: !usageProcess.running
                  onClicked: root.refresh()
                }

                PanelActionButton {
                  iconText: "↗"
                  tooltipText: "Open dashboard"
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                  onClicked: root.openDashboard()
                }
              }
            }
          }

          Row {
            width: parent.width
            spacing: Style.space(8)

            Button {
              text: "Today"
              selected: root.period === "today"
              bordered: true
              foreground: root.foreground
              fontFamily: root.fontFamily
              fontSize: Style.font.bodySmall
              onClicked: root.setPeriod("today")
            }

            Button {
              text: "7 days"
              selected: root.period === "7d"
              bordered: true
              foreground: root.foreground
              fontFamily: root.fontFamily
              fontSize: Style.font.bodySmall
              onClicked: root.setPeriod("7d")
            }
          }

          BorderSurface {
            visible: root.loadError !== ""
            width: parent.width
            implicitHeight: staleText.implicitHeight + Style.space(20)
            color: Qt.rgba(root.urgent.r, root.urgent.g, root.urgent.b, 0.09)
            borderSpec: Border.flat(Qt.rgba(root.urgent.r, root.urgent.g, root.urgent.b, 0.35), 1)
            radius: Style.cornerRadius

            Text {
              id: staleText
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              anchors.leftMargin: Style.space(12)
              anchors.rightMargin: Style.space(12)
              text: root.report
                ? "Refresh failed; showing the previous report. " + root.loadError
                : root.loadError
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }
          }

          Grid {
            id: totalsGrid
            width: parent.width
            columns: 2
            columnSpacing: Style.space(28)
            rowSpacing: Style.space(12)

            Repeater {
              model: 4

              Column {
                required property int index
                width: (totalsGrid.width - totalsGrid.columnSpacing) / 2
                spacing: Style.space(3)

                Text {
                  text: root.totalLabel(index)
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                  font.letterSpacing: 1
                }

                Text {
                  text: root.totalValue(index)
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.title
                  font.bold: true
                }
              }
            }
          }

          Column {
            id: modelSection
            visible: root.currentWindow && root.currentWindow.byModel.length > 0
            width: parent.width
            spacing: Style.space(8)

            PanelSeparator { width: parent.width; foreground: root.foreground }
            PanelSectionHeader {
              text: "BY MODEL"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Repeater {
              model: root.currentWindow ? root.currentWindow.byModel : []
              delegate: Item {
                required property var modelData
                width: modelSection.width
                implicitHeight: modelRow.implicitHeight

                SpendRow {
                  id: modelRow
                  width: parent.width
                  row: modelData
                }
              }
            }
          }

          Column {
            id: sourceSection
            visible: root.currentWindow && root.currentWindow.bySource.length > 0
            width: parent.width
            spacing: Style.space(8)

            PanelSeparator { width: parent.width; foreground: root.foreground }
            PanelSectionHeader {
              text: "BY TOOL"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Repeater {
              model: root.currentWindow ? root.currentWindow.bySource : []
              delegate: Item {
                required property var modelData
                width: sourceSection.width
                implicitHeight: sourceRow.implicitHeight

                SpendRow {
                  id: sourceRow
                  width: parent.width
                  row: modelData
                }
              }
            }
          }

          Text {
            visible: root.currentWindow && !root.emptyReport
              && root.currentWindow.byModel.length === 0
              && root.currentWindow.bySource.length === 0
            width: parent.width
            text: "No usage groups in this period."
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
          }

          Text {
            visible: root.currentWindow && root.emptyReport && !root.loading
            width: parent.width
            text: "No usage recorded in this period."
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
          }

          Text {
            visible: !root.currentWindow && root.loading
            width: parent.width
            text: "Collecting Vibe Usage…"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
          }

          Text {
            visible: root.report !== null
            width: parent.width
            text: Model.updatedText(root.report ? root.report.fetchedAt : "", root.nowMs)
              + (root.loading ? " · refreshing…" : "")
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
          }
        }
      }
    }
  }

  component SpendRow: Column {
    id: spendRow
    property var row: null
    spacing: Style.space(5)

    Row {
      width: parent.width
      spacing: Style.space(8)

      Text {
        text: spendRow.row ? Model.autoTextSafe(spendRow.row.name) : ""
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        elide: Text.ElideRight
        width: Math.max(0, parent.width - costText.implicitWidth - pctText.implicitWidth - Style.space(24))
      }

      Text {
        id: costText
        text: spendRow.row ? Model.formatCost(spendRow.row.cost, false) : ""
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        font.bold: true
      }

      Text {
        id: pctText
        text: spendRow.row ? spendRow.row.pct + "%" : ""
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        width: Style.space(38)
        horizontalAlignment: Text.AlignRight
      }
    }

    Item {
      width: parent.width
      height: Style.space(5)

      Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.track
      }

      Rectangle {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        height: parent.height
        radius: height / 2
        width: parent.width * root.clamp(spendRow.row ? spendRow.row.pct / 100 : 0, 0, 1)
        color: root.foreground
      }
    }
  }
}
