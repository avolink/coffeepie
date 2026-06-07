import QtQuick
import QtQuick.Controls

Item {
    id: root
    width: 1920
    height: 1080

    MouseArea {
        id: mouseAreaExit
        x: 0
        y: 0
        width: 1920
        height: 1080

        Connections {
            target: mouseAreaExit
            onClicked: stackView.clear()
        }

        Rectangle {
            id: mainMenu
            x: 778
            y: 100
            width: 368
            height: 879
            visible: true
            color: "#908f8f"

            MouseArea {
                id: neutralAreaMenu
                x: 0
                y: 1
                width: 368
                height: 878

                Label {
                    id: labelKeepOn
                    x: 0
                    y: 15
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Mantener Encendida")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelModifyMachine
                    x: 0
                    y: 136
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Modificar Máquina")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelDuplicateMachine
                    x: 0
                    y: 284
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Duplicar Máquina")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelSnapshots
                    x: 0
                    y: 437
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Snapshots (Respaldos)")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelRebootShutdown
                    x: 0
                    y: 588
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Reiniciar o Apagar")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelDeleteMachine
                    x: 0
                    y: 740
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Eliminar Máquina")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelOn
                    x: 217
                    y: 70
                    width: 66
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("On")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelOff
                    x: 73
                    y: 70
                    width: 72
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Off")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Button {
                    id: btn_Edit_Machine
                    x: 122
                    y: 168
                    width: 120
                    height: 120
                    icon.height: 120
                    icon.width: 120
                    icon.color: "#00000000"
                    icon.source: "images/Btn_Edit_Machine.png"
                    flat: true

                    Connections {
                        target: btn_Edit_Machine
                       onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                    }
                }

                Button {
                    id: btn_Duplicate_Machine
                    x: 122
                    y: 313
                    width: 120
                    height: 120
                    icon.width: 120
                    icon.source: "images/Btn_Duplicate_Machine.png"
                    icon.height: 120
                    icon.color: "#00000000"
                    flat: true
                }

                Button {
                    id: btn_Snapshots
                    x: 115
                    y: 466
                    width: 136
                    height: 124
                    icon.width: 120
                    icon.source: "images/Btn_Snapshots.png"
                    icon.height: 120
                    icon.color: "#00000000"
                    flat: true
                }

                Button {
                    id: btn_Duplicate_Machine1
                    x: 123
                    y: 620
                    width: 120
                    height: 120
                    icon.width: 120
                    icon.source: "images/Btn_Reboot_Shutdown.png"
                    icon.height: 120
                    icon.color: "#00000000"
                    flat: true
                }

                Switch {
                    id: switchKeepMachineOn
                    x: 145
                    y: 64
                    width: 76
                    height: 51
                    text: qsTr("")
                }

                Switch {
                    id: switchDeleteMachine
                    x: 145
                    y: 784
                    width: 76
                    height: 51
                    text: qsTr("")
                }
            }
        }
    }
}
