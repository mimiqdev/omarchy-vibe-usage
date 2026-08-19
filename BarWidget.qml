import QtQuick
import qs.Commons
import qs.Ui

// The bar slot owns routing and injects its button into the panel. Keeping the
// panel in a Loader lets the same widget identity participate in popout
// handoff and keyboard summoning.
BarWidget {
  id: root
  moduleName: "cafe.vibe.usage"

  readonly property var panelItem: panelLoader.item
  readonly property bool opened: panelItem ? panelItem.opened === true : false
  readonly property bool popoutSwitchClosing: panelItem
    ? panelItem.popoutSwitchClosing === true
    : false

  function injectPanel() {
    var target = panelItem
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  function open() {
    if (panelItem) panelItem.open()
  }

  function close() {
    if (panelItem) panelItem.close()
  }

  function toggle() {
    if (panelItem) panelItem.toggle()
  }

  function closeForPopoutSwitch() {
    if (panelItem) panelItem.closeForPopoutSwitch()
  }

  function refresh() {
    if (panelItem) panelItem.refresh()
  }

  function launchDashboard() {
    var url = panelItem && typeof panelItem.dashboardUrl === "function"
      ? panelItem.dashboardUrl()
      : "https://vibecafe.ai/usage"
    if (root.bar) root.bar.run("omarchy launch browser " + url)
    root.close()
  }

  visible: panelItem && panelItem.label !== ""
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.panelItem ? root.panelItem.barText() : "…"
    fontSize: Style.font.bodySmall
    active: root.panelItem ? root.panelItem.alarming : false
    tooltipText: root.panelItem ? root.panelItem.tooltipText() : "Vibe Usage"
    horizontalMargin: 8.5

    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) root.launchDashboard()
      else if (buttonCode === Qt.MiddleButton) root.refresh()
      else root.toggle()
    }
  }
}
