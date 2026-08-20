import QtQuick
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model
import "Locale.js" as Locale
import "RangeCache.js" as Cache

// The panel owns one short-lived helper process and keeps the last successful
// report when a later request fails. The bar widget remains the shell-facing
// identity.
Panel {
  id: root
  moduleName: "mimiqdev.vibe-usage"
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
  readonly property string uiLocale: Locale.normalizeLocale(Qt.locale().name)

  // Keep one independent report state per server range. Navigation only
  // selects a state; it never overwrites another range's request or report.
  property var rangeStates: Cache.initialStates()
  property string range: Model.normalizeRange(setting("period", "today"))
  // This is presentation-only state. Changing it never restarts the helper.
  property string metric: "cost"
  property int requestSerial: 0
  property int activeRequest: 0
  property string activeRequestRange: ""
  property string processRange: ""
  property var pendingRanges: []
  property var pendingForce: ({})
  property string commandStdout: ""
  property string commandStderr: ""
  property double nowMs: Date.now()

  readonly property int refreshIntervalSec: Math.max(30, Math.min(600,
    Number(setting("refreshIntervalSec", 120)) || 120))
  readonly property bool showTokens: setting("showTokens", true) !== false
  readonly property bool hideWhenEmpty: setting("hideWhenEmpty", false) === true
  readonly property var currentState: rangeStates[range] || rangeStates.today
  readonly property var cachedReport: currentState ? currentState.report : null
  readonly property bool reportMatchesRange: !!(cachedReport
    && cachedReport.ok === true && cachedReport.range === range)
  readonly property var currentReport: reportMatchesRange ? cachedReport : null
  // Keep this compatibility property for bar/panel callers that use report.
  readonly property var report: currentReport
  readonly property bool loading: currentState
    ? currentState.loading === true
      || (!currentReport && currentState.errorCode === "")
    : false
  readonly property string loadError: currentState && currentState.errorCode
    ? Locale.errorText(currentState.errorCode, null, uiLocale) : ""
  readonly property bool initRequired: currentState
    ? currentState.initRequired === true : false
  readonly property double lastSuccessfulMs: currentState
    ? Number(currentState.lastSuccessfulMs) || 0 : 0
  readonly property var totals: currentReport ? currentReport.totals
    : ({ cost: 0, tokens: 0, cachedTokens: 0, sessions: 0, activeSeconds: 0 })
  readonly property var series: currentReport ? currentReport.series : []
  readonly property var activeByHost: currentReport
    ? (metric === "tokens" ? currentReport.byHostTokens : currentReport.byHost)
    : []
  readonly property var activeBySource: currentReport
    ? (metric === "tokens" ? currentReport.bySourceTokens : currentReport.bySource)
    : []
  readonly property var activeByModel: currentReport
    ? (metric === "tokens" ? currentReport.byModelTokens : currentReport.byModel)
    : []
  readonly property real maxSeriesValue: Model.maxSeriesValue(series, metric)
  readonly property bool emptyReport: !!currentReport
    && totals.cost === 0 && totals.tokens === 0 && totals.cachedTokens === 0
    && totals.sessions === 0 && totals.activeSeconds === 0
  readonly property bool showInitState: initRequired && !currentReport
  readonly property bool showReportBody: !!currentReport && !showInitState
  readonly property bool alarming: loadError !== ""
  readonly property string label: hideWhenEmpty && emptyReport ? "" : barText()

  function barText() {
    return Model.barText(report, range, showTokens, vertical, loading, loadError)
  }

  function tooltipText() {
    return Model.tooltipText(report, range, loading, loadError, uiLocale, Locale)
  }

  function dashboardUrl() {
    return Model.safeDashboard(report ? report.dashboard : "")
  }

  function periodMeta() {
    var meta = Model.periodMetaLabel(range, uiLocale, Locale)
    if (!currentReport)
      return meta + " · " + Locale.t(
        loading ? "status.loading" : "status.unavailable",
        null,
        uiLocale
      )
    meta += " · " + Locale.t(
      "meta.summary",
      {
        sessions: totals.sessions,
        active: Model.formatActive(totals.activeSeconds)
      },
      uiLocale
    )
    if (loadError !== "")
      meta += " · " + Locale.t("status.stale", null, uiLocale)
    return meta
  }

  function totalLabel(index) {
    return Locale.t(
      ["card.cost", "card.tokens", "card.cache", "card.active"][index] || "",
      null,
      uiLocale
    )
  }

  function totalValue(index) {
    if (index === 0) return Model.formatCost(totals.cost, false)
    if (index === 1) return Model.formatTokens(totals.tokens)
    if (index === 2) return Model.formatTokens(totals.cachedTokens)
    return Model.formatActive(totals.activeSeconds)
  }

  function rangeNames() {
    return Cache.rangeNames()
  }

  function rangeState(value) {
    return Cache.stateFor(rangeStates, value)
  }

  // Assign a new map so bindings to currentState/currentReport update even
  // though the individual cached entries are plain JavaScript objects.
  function updateRangeState(value, changes) {
    rangeStates = Cache.updateStates(rangeStates, value, changes)
  }

  function isRangeFresh(value) {
    return Cache.isFresh(
      rangeStates,
      value,
      Date.now(),
      refreshIntervalSec * 1000,
    )
  }

  function queueRange(value, force, priority) {
    var selected = Model.normalizeRange(value)
    var queued = Cache.enqueue(
      pendingRanges,
      pendingForce,
      selected,
      force === true,
      priority === true,
    )
    pendingRanges = queued.ranges
    pendingForce = queued.force
    updateRangeState(selected, { loading: true })
  }

  function requestRange(value, force, priority) {
    var selected = Model.normalizeRange(value)
    var state = rangeState(selected)
    // A queued or active request already covers this range. Navigation must
    // not cancel it or create a duplicate, but a queued tab can move ahead of
    // other background work when it becomes the visible range.
    if (state && state.loading === true) {
      if (selected !== activeRequestRange && priority === true
          && pendingRanges.indexOf(selected) >= 0) {
        var reprioritized = Cache.enqueue(
          pendingRanges,
          pendingForce,
          selected,
          force === true,
          true,
        )
        pendingRanges = reprioritized.ranges
        pendingForce = reprioritized.force
      }
      return false
    }
    if (!Cache.needsRequest(
      rangeStates,
      selected,
      force === true,
      Date.now(),
      refreshIntervalSec * 1000,
    )) return false
    queueRange(selected, force === true, priority === true)
    pumpRequests()
    return true
  }

  function pumpRequests() {
    if (usageProcess.running || activeRequest !== 0) return
    while (pendingRanges.length > 0) {
      var selected = pendingRanges.shift()
      var force = pendingForce[selected] === true
      delete pendingForce[selected]
      if (force !== true && isRangeFresh(selected)) {
        updateRangeState(selected, { loading: false })
        continue
      }
      commandStdout = ""
      commandStderr = ""
      processRange = selected
      activeRequestRange = selected
      activeRequest = ++requestSerial
      usageProcess.running = true
      return
    }
  }

  function refreshStaleRanges() {
    var selected = range
    // The selected range has priority, but only loaded ranges are considered
    // for background refresh. Opening the panel never fetches all four.
    requestRange(selected, false, true)
    var names = rangeNames()
    for (var i = 0; i < names.length; i++) {
      var name = names[i]
      var state = rangeState(name)
      if (name !== selected && state && state.report && !isRangeFresh(name))
        requestRange(name, false, false)
    }
  }

  function setRange(value) {
    var next = Model.normalizeRange(value)
    if (range !== next) {
      range = next
      if (panelFlick) panelFlick.contentY = 0
    }
    // A fresh report is shown immediately. Missing/stale reports are queued
    // without discarding the selected range's previous successful report.
    requestRange(next, false, true)
  }

  function switchRange(delta) {
    var ranges = rangeNames()
    var index = ranges.indexOf(range)
    if (index < 0) index = 0
    index = Math.max(0, Math.min(ranges.length - 1, index + (delta < 0 ? -1 : 1)))
    setRange(ranges[index])
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value))
  }

  function switchPanel(direction) {
    if (bar && typeof bar.switchPanelFrom === "function")
      return bar.switchPanelFrom(barIdentity, direction)
    return false
  }

  function finishRefresh(requestId, requestedRange) {
    if (requestId !== activeRequest || requestedRange !== activeRequestRange) return

    var parsed = Model.parseReport(commandStdout)
    var finishedAt = Date.now()
    activeRequest = 0
    activeRequestRange = ""
    processRange = ""

    if (parsed.ok && parsed.range === requestedRange) {
      updateRangeState(requestedRange, {
        report: parsed,
        loading: false,
        errorCode: "",
        initRequired: false,
        lastSuccessfulMs: finishedAt
      })
      if (requestedRange === range) nowMs = finishedAt
    } else {
      var errorCode = parsed.ok
        ? "range_mismatch"
        : parsed.errorCode
      if (!errorCode)
        errorCode = Locale.errorCodeFromMessage(parsed.error || commandStderr)
      errorCode = Locale.normalizeErrorCode(errorCode)
      // Do not replace report: a failed refresh leaves the previous report
      // visible for this range and records only the stale/error state.
      updateRangeState(requestedRange, {
        loading: false,
        errorCode: errorCode,
        initRequired: Locale.requiresInit(errorCode)
      })
    }
    pumpRequests()
  }

  function refresh() {
    requestRange(range, true, true)
  }

  // Qt.resolvedUrl returns a file:// URL. Process argv needs a local path or
  // python3 tries to open the literal URL and writes nothing to stdout.
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
      // Revisit only the selected range. Other loaded ranges are refreshed by
      // the normal timer, never eagerly just because the panel opened.
      root.requestRange(range, false, true)
      Qt.callLater(function() { keyCatcher.forceActiveFocus() })
    }
  }

  Timer {
    interval: root.refreshIntervalSec * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refreshStaleRanges()
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
    // Keep the command bound to the range captured when the process started;
    // the visible tab can change while this request is still running.
    command: ["python3", root.helperPath(), "--range", root.processRange]

    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.commandStdout = text
    }

    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.commandStderr = text
    }

    onExited: {
      var finishedRequest = root.activeRequest
      var finishedRange = root.activeRequestRange
      Qt.callLater(function() {
        root.finishRefresh(finishedRequest, finishedRange)
      })
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(500))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(760))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent

      onMoveRequested: function(dx, dy) {
        if (dx !== 0) root.switchRange(dx)
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
            title: Locale.t("brand", null, root.uiLocale)
            detail: root.currentReport
              ? Model.formatMetric(
                root.metric === "tokens" ? root.totals.tokens : root.totals.cost,
                root.metric,
                false
              )
              : ""
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
                  tooltipText: Locale.t("action.refresh", null, root.uiLocale)
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                  // Refresh is scoped to the visible range. A request for a
                  // different range may continue in the background.
                  enabled: !root.loading
                  onClicked: root.refresh()
                }

                PanelActionButton {
                  iconText: "↗"
                  tooltipText: Locale.t("action.dashboard", null, root.uiLocale)
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                  onClicked: root.openDashboard()
                }
              }
            }
          }

          Row {
            width: parent.width
            spacing: Style.space(4)

            Repeater {
              model: ["today", "24h", "7d", "30d"]

              Button {
                required property string modelData
                text: Model.periodLabel(modelData, root.uiLocale, Locale)
                selected: root.range === modelData
                bordered: true
                foreground: root.foreground
                fontFamily: root.fontFamily
                fontSize: Style.font.bodySmall
                onClicked: root.setRange(modelData)
              }
            }
          }

          Row {
            width: parent.width
            spacing: Style.space(4)

            Repeater {
              model: ["cost", "tokens"]

              Button {
                required property string modelData
                text: Locale.t("metric." + modelData, null, root.uiLocale)
                selected: root.metric === modelData
                bordered: true
                foreground: root.foreground
                fontFamily: root.fontFamily
                fontSize: Style.font.bodySmall
                onClicked: root.metric = modelData
              }
            }
          }

          BorderSurface {
            visible: root.loadError !== "" && !root.showInitState
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
              text: root.currentReport
                ? Locale.t("error.stalePrefix", null, root.uiLocale) + root.loadError
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
            visible: root.showReportBody
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
            id: trendSection
            visible: root.showReportBody
            width: parent.width
            spacing: Style.space(8)

            PanelSeparator { width: parent.width; foreground: root.foreground }
            PanelSectionHeader {
              text: Locale.t("section.trend", null, root.uiLocale)
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Item {
              id: trend
              width: parent.width
              height: root.series.length > 0 ? Style.space(104) : Style.space(28)

              Row {
                anchors.fill: parent
                anchors.bottomMargin: Style.space(18)
                // Zero spacing keeps every hourly/daily bar, including the
                // highlighted last bar, inside the chart width.
                spacing: 0

                Repeater {
                  model: root.series

                  Item {
                    required property var modelData
                    required property int index
                    width: trend.width / Math.max(1, root.series.length)
                    height: trend.height - Style.space(18)

                    Rectangle {
                      anchors.horizontalCenter: parent.horizontalCenter
                      anchors.bottom: parent.bottom
                      width: Math.max(Style.space(3), parent.width - 2)
                      height: root.maxSeriesValue > 0
                        ? Math.max(2, (Number(Model.metricValue(modelData, root.metric))
                          / root.maxSeriesValue)
                          * (parent.height - Style.space(12)))
                        : 2
                      radius: Math.min(2, height / 2)
                      color: index === root.series.length - 1 ? root.foreground : root.track
                    }

                    Text {
                      visible: index === 0 || index === root.series.length - 1
                      anchors.top: parent.bottom
                      anchors.topMargin: Style.space(2)
                      width: parent.width
                      text: modelData.label
                      color: root.dim
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      horizontalAlignment: index === 0 ? Text.AlignLeft : Text.AlignRight
                      elide: Text.ElideRight
                    }
                  }
                }
              }

              Text {
                visible: root.series.length === 0
                anchors.fill: parent
                text: root.emptyReport
                  ? Locale.t("empty.noUsage", null, root.uiLocale)
                  : Locale.t("empty.noTrend", null, root.uiLocale)
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
              }
            }
          }

          Column {
            id: sourceSection
            visible: root.showReportBody && root.activeBySource.length > 0
            width: parent.width
            spacing: Style.space(8)

            PanelSeparator { width: parent.width; foreground: root.foreground }
            PanelSectionHeader {
              text: Locale.t("section.tool", null, root.uiLocale)
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Repeater {
              model: root.activeBySource
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

          Column {
            id: modelSection
            visible: root.showReportBody && root.activeByModel.length > 0
            width: parent.width
            spacing: Style.space(8)

            PanelSeparator { width: parent.width; foreground: root.foreground }
            PanelSectionHeader {
              text: Locale.t("section.model", null, root.uiLocale)
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Repeater {
              model: root.activeByModel
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
            id: hostSection
            visible: root.showReportBody && root.activeByHost.length > 0
            width: parent.width
            spacing: Style.space(8)

            PanelSeparator { width: parent.width; foreground: root.foreground }
            PanelSectionHeader {
              text: Locale.t("section.host", null, root.uiLocale)
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Repeater {
              model: root.activeByHost
              delegate: Item {
                required property var modelData
                width: hostSection.width
                implicitHeight: hostRow.implicitHeight

                SpendRow {
                  id: hostRow
                  width: parent.width
                  row: modelData
                }
              }
            }
          }

          Column {
            visible: root.showInitState
            width: parent.width
            spacing: Style.space(8)

            Text {
              width: parent.width
              text: Locale.t("init.title", null, root.uiLocale)
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.title
              font.bold: true
              horizontalAlignment: Text.AlignHCenter
            }

            Text {
              width: parent.width
              text: Locale.t("init.instructions", null, root.uiLocale)
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              wrapMode: Text.WordWrap
              horizontalAlignment: Text.AlignHCenter
            }
          }

          Text {
            visible: !root.currentReport && !root.loading && !root.showInitState
              && root.loadError === ""
            width: parent.width
            text: Locale.t("empty.noReport", null, root.uiLocale)
            textFormat: Text.PlainText
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
          }

          Text {
            visible: !root.currentReport && root.loading
            width: parent.width
            text: Locale.t("loading.fetching", null, root.uiLocale)
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
          }

          Text {
            visible: root.currentReport
            width: parent.width
            text: Model.updatedText(
              root.currentReport ? root.currentReport.fetchedAt : "",
              root.nowMs,
              root.uiLocale,
              Locale
            ) + (root.loading
              ? " · " + Locale.t("status.refreshing", null, root.uiLocale)
              : "")
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
        width: Math.max(0, parent.width - metricText.implicitWidth - pctText.implicitWidth - Style.space(24))
      }

      Text {
        id: metricText
        text: spendRow.row
          ? Model.formatMetric(
            Model.metricValue(spendRow.row, root.metric),
            root.metric,
            false
          )
          : ""
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
