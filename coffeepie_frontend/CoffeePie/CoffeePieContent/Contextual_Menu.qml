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
            x: 776
            y: 51
            width: 368
            height: 990
            visible: true
            color: "#908f8f"

            MouseArea {
                id: neutralAreaMenu
                x: 0
                y: 1
                width: 368
                height: 989

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
                    x: -7
                    y: 214
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
                    x: -7
                    y: 362
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
                    x: -7
                    y: 515
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
                    x: -7
                    y: 666
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
                    x: -7
                    y: 824
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
                    y: 63
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
                    y: 63
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
                    x: 115
                    y: 246
                    width: 120
                    height: 120
                    visible: true
                    icon.height: 120
                    icon.width: 120
                    icon.color: "#00000000"
                    icon.source: "images/Contextual_Menu/Btn_Edit_Machine.png"
                    flat: true

                    Connections {
                        target: btn_Edit_Machine
                        onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                    }
                }

                Button {
                    id: btn_Duplicate_Machine
                    x: 115
                    y: 391
                    width: 120
                    height: 120
                    icon.width: 120
                    icon.source: "images/Contextual_Menu/Btn_Duplicate_Machine.png"
                    icon.height: 120
                    icon.color: "#00000000"
                    flat: true
                }

                Button {
                    id: btn_Snapshots
                    x: 108
                    y: 544
                    width: 136
                    height: 124
                    icon.width: 120
                    icon.source: "images/Contextual_Menu/Btn_Snapshots.png"
                    icon.height: 120
                    icon.color: "#00000000"
                    flat: true
                }

                Button {
                    id: btn_Duplicate_Machine1
                    x: 116
                    y: 698
                    width: 120
                    height: 120
                    icon.width: 120
                    icon.source: "images/Contextual_Menu/Btn_Reboot_Shutdown.png"
                    icon.height: 120
                    icon.color: "#00000000"
                    flat: true
                }

                Switch {
                    id: switchKeepMachineOn
                    x: 145
                    y: 57
                    width: 76
                    height: 51
                    text: qsTr("")
                }

                Image {
                    id: blank_Square1
                    x: 184
                    y: 111
                    source: "images/Blank_Square.png"
                    fillMode: Image.PreserveAspectFit

                    Button {
                        id: btn_Stop
                        x: 8
                        y: 8
                        width: 88
                        height: 88
                        visible: true
                        text: qsTr("")
                        flat: true
                        clip: false
                        icon.height: 120
                        icon.width: 120
                        icon.color: "#00000000"
                        icon.source: "images/Contextual_Menu/Btn_Stop.png"
                    }
                }

                Image {
                    id: blank_Square
                    x: 63
                    y: 111
                    source: "images/Blank_Square.png"
                    fillMode: Image.PreserveAspectFit

                    Button {
                        id: btn_Play_Pause
                        x: 8
                        y: 8
                        width: 88
                        height: 88
                        text: qsTr("")
                        flat: true
                        icon.height: 120
                        icon.width: 120
                        icon.color: "#00000000"
                        icon.source: "images/Contextual_Menu/Btn_Play_Pause.png"
                    }
                }

                Button {
                    id: btnDeleteMachine
                    x: 117
                    y: 858
                    width: 120
                    height: 123
                    text: qsTr("")
                    icon.height: 120
                    icon.width: 120
                    icon.color: "#00000000"
                    flat: true
                    icon.source: "images/Contextual_Menu/Btn_Delete.png"
                }



            }
        }
    }
}
