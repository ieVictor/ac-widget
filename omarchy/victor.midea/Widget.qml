import "." as Midea
import "icons" as Icons
import "Model.js" as Model
import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

Panel {
    id: root

    property real draftTemperature: 24
    property string draftMode: "COOL"
    property bool draftDirty: false
    readonly property var backend: Midea.Backend
    readonly property color ink: Color.popups.text
    readonly property color aiGreen: Model.aiColor(Color.popups.background)
    readonly property var deviceState: backend.state
    readonly property var capabilities: backend.capabilities
    readonly property bool changed: deviceState !== null && (draftTemperature !== deviceState.target_temperature || draftMode !== deviceState.mode)

    function configureBackend() {
        backend.configure(setting("executable", ""), setting("refreshSeconds", 60));
    }

    function resetDraft() {
        if (!deviceState)
            return;

        draftTemperature = deviceState.target_temperature;
        draftMode = deviceState.mode;
        modeControl.value = draftMode;
        draftDirty = false;
    }

    function open() {
        resetDraft();
        root.controller.show();
        backend.refresh();
    }

    function diagnostics() {
        return JSON.stringify({
            "opened": root.opened,
            "busy": backend.busy,
            "fresh": backend.fresh,
            "state": backend.state,
            "capabilitiesFromDevice": backend.capabilitiesFromDevice,
            "error": backend.errorMessage,
            "controlsReady": backend.controlsReady,
            "lastUpdated": backend.lastUpdated,
            "popupWidth": panel.contentWidth,
            "popupHeight": panel.contentHeight,
            "popupX": panel.cardOrigin.x,
            "popupY": panel.cardOrigin.y,
            "barPosition": bar ? bar.position : "",
            "hasChanges": changed
        });
    }

    moduleName: "victor.midea"
    manageIpc: false
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    onSettingsChanged: configureBackend()
    Component.onCompleted: {
        configureBackend();
        backend.refresh();
    }

    Connections {
        function onConfirmed() {
            if (!root.opened || !root.draftDirty || (root.backend.pendingControl && root.backend.pendingAction !== "ieco" && root.backend.pendingAction !== "display" && root.backend.pendingAction !== "swing"))
                root.resetDraft();
        }

        target: root.backend
    }

    WidgetButton {
        id: button

        anchors.fill: parent
        bar: root.bar
        text: "󰜗 " + (!backend.state ? "…" : !backend.fresh ? "—" : backend.state.power ? Model.temperatureNumber(backend.state.target_temperature) + "°" : "Desl.")
        foreground: backend.fresh && backend.state.power ? Color.accent : root.barForeground
        fontSize: Style.font.body
        tooltipText: "Ar-condicionado · " + (!backend.fresh ? "sem leitura atualizada" : backend.state.power ? "ligado" : "desligado") + "\nClique para abrir os controles."
        onPressed: function (mouseButton) {
            if (mouseButton === Qt.MiddleButton)
                backend.refresh();
            else
                root.toggle();
        }
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: "Abrir controles do ar-condicionado"
        Keys.onReturnPressed: root.toggle()
        Keys.onSpacePressed: root.toggle()
    }

    KeyboardPanel {
        id: panel

        anchorItem: button
        owner: root
        bar: root.bar
        open: root.opened
        focusTarget: contentFocus
        contentWidth: panel.fittedContentWidth(Style.space(360))
        contentHeight: panel.fittedContentHeight(column.implicitHeight)

        FocusScope {
            id: contentFocus

            anchors.fill: parent
            Keys.onEscapePressed: root.close()

            Flickable {
                anchors.fill: parent
                contentWidth: width
                contentHeight: column.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height

                Column {
                    id: column

                    width: parent.width
                    spacing: Style.space(16)

                    Row {
                        width: parent.width
                        spacing: Style.space(8)

                        Column {
                            width: parent.width - powerButton.width - parent.spacing
                            spacing: Style.space(4)

                            Text {
                                text: "Ar-condicionado"
                                textFormat: Text.PlainText
                                color: root.ink
                                font.family: Style.font.family
                                font.pixelSize: Style.font.heading
                                font.bold: true
                            }

                            Text {
                                text: !backend.fresh ? "Estado não confirmado" : root.deviceState.power ? "Ligado · conexão local" : "Desligado · conexão local"
                                textFormat: Text.PlainText
                                color: root.ink
                                font.family: Style.font.family
                                font.pixelSize: Style.font.bodySmall
                            }
                        }

                        Button {
                            id: powerButton

                            text: root.deviceState && root.deviceState.power ? "Desligar" : "Ligar ar"
                            iconText: "⏻"
                            enabled: backend.controlsReady
                            opacity: enabled ? 1 : 0.45
                            focusable: true
                            bordered: true
                            foreground: root.ink
                            Accessible.role: Accessible.Button
                            Accessible.name: text
                            onClicked: backend.setPower(!root.deviceState.power)
                        }
                    }

                    Column {
                        width: parent.width
                        spacing: Style.space(8)

                        Text {
                            text: "Temperatura desejada"
                            textFormat: Text.PlainText
                            color: root.ink
                            font.family: Style.font.family
                            font.pixelSize: Style.font.body
                        }

                        Row {
                            width: parent.width
                            spacing: Style.space(12)

                            Button {
                                text: "−"
                                implicitWidth: Style.space(44)
                                implicitHeight: Style.space(44)
                                foreground: root.ink
                                bordered: true
                                focusable: true
                                enabled: backend.controlsReady && draftTemperature > capabilities.min_target_temperature
                                opacity: enabled ? 1 : 0.45
                                Accessible.role: Accessible.Button
                                Accessible.name: "Diminuir temperatura em meio grau"
                                onClicked: {
                                    root.draftTemperature = Model.clampTemperature(root.draftTemperature - 0.5, capabilities);
                                    root.draftDirty = true;
                                }
                            }

                            Text {
                                width: parent.width - Style.space(112)
                                height: Style.space(44)
                                text: Model.temperatureNumber(root.deviceState ? draftTemperature : null) + " °C"
                                textFormat: Text.PlainText
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                color: root.ink
                                font.family: Style.font.family
                                font.pixelSize: Style.font.displayLarge
                                font.bold: true
                                Accessible.role: Accessible.StaticText
                                Accessible.name: "Temperatura desejada: " + text
                            }

                            Button {
                                text: "+"
                                implicitWidth: Style.space(44)
                                implicitHeight: Style.space(44)
                                foreground: root.ink
                                bordered: true
                                focusable: true
                                enabled: backend.controlsReady && draftTemperature < capabilities.max_target_temperature
                                opacity: enabled ? 1 : 0.45
                                Accessible.role: Accessible.Button
                                Accessible.name: "Aumentar temperatura em meio grau"
                                onClicked: {
                                    root.draftTemperature = Model.clampTemperature(root.draftTemperature + 0.5, capabilities);
                                    root.draftDirty = true;
                                }
                            }
                        }

                        Text {
                            text: "Ambiente: " + Model.temperature(root.deviceState ? root.deviceState.indoor_temperature : null)
                            textFormat: Text.PlainText
                            color: root.ink
                            font.family: Style.font.family
                            font.pixelSize: Style.font.bodySmall
                        }
                    }

                    Dropdown {
                        id: modeControl

                        width: parent.width
                        label: "Modo"
                        options: Model.modes(capabilities)
                        value: root.draftMode
                        foreground: root.ink
                        background: Color.popups.background
                        enabled: backend.controlsReady
                        opacity: enabled ? 1 : 0.45
                        Accessible.name: "Modo do ar-condicionado"
                        onChanged: function (value) {
                            root.draftMode = value;
                            root.draftDirty = true;
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: Style.space(12)
                        visible: capabilities && capabilities.supports_ieco === true

                        Button {
                            text: capabilities && capabilities.ieco_number === 8 ? "AI" : "iECO"
                            implicitWidth: Style.space(44)
                            implicitHeight: Style.space(44)
                            foreground: root.aiGreen
                            bordered: true
                            focusable: true
                            enabled: backend.controlsReady && Model.iecoReady(root.deviceState, capabilities)
                            opacity: enabled ? 1 : 0.45
                            Accessible.role: Accessible.Button
                            Accessible.checkable: true
                            Accessible.checked: root.deviceState !== null && root.deviceState.ieco === true
                            Accessible.name: root.deviceState && root.deviceState.ieco === true ? "Desativar economia inteligente" : "Ativar economia inteligente"
                            onClicked: backend.setIeco(!root.deviceState.ieco)
                        }

                        Column {
                            width: parent.width - Style.space(56)
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: Style.space(4)
                            Text {
                                text: "Economia inteligente"
                                color: root.ink
                                font.family: Style.font.family
                                font.pixelSize: Style.font.body
                            }
                            Text {
                                width: parent.width
                                text: !backend.fresh || !root.deviceState || root.deviceState.ieco === null ? "Estado não confirmado" : root.deviceState.ieco ? "Ativada · " + (capabilities.ieco_number === 8 ? "ECOMaster" : "iECO") : !root.deviceState.power || root.deviceState.mode !== "COOL" ? "Desativada · ligue em Refrigerar" : "Desativada · " + (capabilities.ieco_number === 8 ? "ECOMaster" : "iECO")
                                color: root.ink
                                wrapMode: Text.WordWrap
                                font.family: Style.font.family
                                font.pixelSize: Style.font.bodySmall
                            }
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: Style.space(12)
                        visible: capabilities && capabilities.supports_display_control === true

                        Button {
                            id: displayButton
                            text: "LED"
                            implicitWidth: Style.space(44)
                            implicitHeight: Style.space(44)
                            enabled: backend.controlsReady && Model.displayReady(root.deviceState, capabilities)
                            opacity: enabled ? 1 : 0.45
                            foreground: root.ink
                            bordered: true
                            focusable: true
                            Accessible.role: Accessible.Button
                            Accessible.name: root.deviceState && root.deviceState.display_on === true ? "Desligar visor LED" : "Ligar visor LED"
                            Accessible.checkable: true
                            Accessible.checked: root.deviceState !== null && root.deviceState.display_on === true
                            onClicked: backend.setDisplay(!root.deviceState.display_on)
                        }

                        Column {
                            width: parent.width - Style.space(56)
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: Style.space(4)
                            Text {
                                text: "Visor LED"
                                color: root.ink
                                font.family: Style.font.family
                                font.pixelSize: Style.font.body
                            }
                            Text {
                                text: !backend.fresh || !root.deviceState || root.deviceState.display_on === null ? "Estado não confirmado" : root.deviceState.display_on ? "Ativado" : "Desativado"
                                color: root.ink
                                font.family: Style.font.family
                                font.pixelSize: Style.font.bodySmall
                            }
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: Style.space(12)
                        visible: capabilities && capabilities.supports_vertical_swing === true

                        Button {
                            implicitWidth: Style.space(44)
                            implicitHeight: Style.space(44)
                            enabled: backend.controlsReady && Model.swingReady(root.deviceState, capabilities)
                            opacity: enabled ? 1 : 0.45
                            foreground: root.ink
                            bordered: true
                            focusable: true
                            tooltipText: "Swing vertical: clique para a próxima posição.\nParado → 1 → 2 → 3 → 4 → 5 → oscilando."
                            Accessible.role: Accessible.Button
                            Accessible.name: "Próxima direção do Swing vertical"
                            Accessible.description: Model.swingLabel(root.deviceState ? root.deviceState.vertical_swing_state : null)
                            onClicked: backend.cycleSwing()

                            Icons.SwingIcon {
                                anchors.centerIn: parent
                                width: Style.space(18)
                                height: Style.space(28)
                                ink: root.ink
                                swingState: backend.fresh && root.deviceState ? (root.deviceState.vertical_swing_state || "") : ""
                            }
                        }

                        Column {
                            width: parent.width - Style.space(56)
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: Style.space(4)
                            Text {
                                text: "Swing vertical"
                                color: root.ink
                                font.family: Style.font.family
                                font.pixelSize: Style.font.body
                            }
                            Text {
                                text: !backend.fresh ? "Estado não confirmado" : root.deviceState && !root.deviceState.power ? "Ligue o ar para ajustar" : Model.swingLabel(root.deviceState ? root.deviceState.vertical_swing_state : null)
                                color: root.ink
                                font.family: Style.font.family
                                font.pixelSize: Style.font.bodySmall
                            }
                        }
                    }

                    Button {
                        width: parent.width
                        text: backend.busy && backend.pendingControl ? "Confirmando no aparelho…" : "Aplicar ajustes"
                        enabled: backend.controlsReady && root.changed && Model.validDraft(draftTemperature, draftMode, capabilities)
                        opacity: enabled ? 1 : 0.45
                        foreground: root.ink
                        bordered: true
                        focusable: true
                        Accessible.role: Accessible.Button
                        Accessible.name: "Aplicar temperatura e modo sem alterar liga/desliga"
                        onClicked: backend.apply(root.draftTemperature, root.draftMode)
                    }

                    Text {
                        width: parent.width
                        visible: backend.errorMessage !== ""
                        text: backend.errorMessage
                        textFormat: Text.PlainText
                        wrapMode: Text.WordWrap
                        color: root.ink
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                    }

                    Row {
                        width: parent.width
                        spacing: Style.space(8)

                        Text {
                            width: parent.width - refreshButton.width - parent.spacing
                            anchors.verticalCenter: parent.verticalCenter
                            text: backend.busy ? "Consultando o aparelho…" : backend.lastUpdated > 0 ? "Leitura: " + Qt.formatTime(new Date(backend.lastUpdated), "HH:mm:ss") : "Aguardando leitura"
                            textFormat: Text.PlainText
                            color: root.ink
                            font.family: Style.font.family
                            font.pixelSize: Style.font.bodySmall
                            elide: Text.ElideRight
                        }

                        Button {
                            id: refreshButton

                            text: "Atualizar"
                            enabled: !backend.busy
                            opacity: enabled ? 1 : 0.45
                            foreground: root.ink
                            focusable: true
                            Accessible.role: Accessible.Button
                            Accessible.name: "Atualizar estado do ar-condicionado"
                            onClicked: backend.refresh()
                        }
                    }
                }
            }
        }
    }
}
