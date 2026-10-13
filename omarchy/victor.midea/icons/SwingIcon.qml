import QtQuick

Item {
    id: root
    property string swingState: ""
    property color ink: "white"
    implicitWidth: 18
    implicitHeight: 28
    readonly property int activeLines: swingState === "AUTO" ? 5 : /^POS_[1-5]$/.test(swingState) ? 1 : 0

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.color: root.ink
        border.width: Math.max(1, width / 18)

        Repeater {
            model: 5
            delegate: Rectangle {
                required property int index
                objectName: "swingLine" + index
                width: parent.width * 0.65
                height: Math.max(1, parent.height / 28)
                x: (parent.width - width) / 2
                y: parent.height * (0.15 + index * 0.175)
                color: root.ink
                visible: root.swingState === "AUTO" || root.swingState === "POS_" + (index + 1)
            }
        }
    }
}
