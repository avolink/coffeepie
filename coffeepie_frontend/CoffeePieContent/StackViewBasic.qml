import QtQuick
import QtQuick.Controls

Item {
    id: root
    width: 1920
    height: 824

    StackView {
        id: stackViewBasic
        x: 0
        y: 0
        width: 1920
        height: 788
    }

    ScrollView {
        id: scrollView
        x: 3
        y: 1
        width: 1917
        height: 826
        rotation: -0.066


        Button {
            id: buttonNewMachine2
            x: 684
            y: 29
            width: 550
            height: 375
            icon.width: 537
            icon.source: "images/New_Machine_Button.png"
            icon.height: 360
            icon.color: "#007a2828"
            flat: true
            Connections {
                target: buttonNewMachine2
                onClicked: stackView.push("Basic_OS_Selection.qml")
            }
        }

        Button {
            id: buttonNewMachine3
            x: 1300
            y: 28
            width: 550
            height: 375
            icon.width: 537
            icon.source: "images/New_Machine_Button.png"
            icon.height: 360
            icon.color: "#007a2828"
            flat: true
            Connections {
                target: buttonNewMachine3
                onClicked: stackView.push("Basic_OS_Selection.qml")
            }
        }

        Button {
            id: buttonNewMachine4
            x: 68
            y: 428
            width: 550
            height: 375
            icon.width: 537
            icon.source: "images/New_Machine_Button.png"
            icon.height: 360
            icon.color: "#007a2828"
            flat: true
            Connections {
                target: buttonNewMachine4
                onClicked: stackView.push("Basic_OS_Selection.qml")
            }
        }

        Button {
            id: buttonNewMachine5
            x: 684
            y: 429
            width: 550
            height: 375
            icon.width: 537
            icon.source: "images/New_Machine_Button.png"
            icon.height: 360
            icon.color: "#007a2828"
            flat: true
            Connections {
                target: buttonNewMachine5
                onClicked: stackView.push("Basic_OS_Selection.qml")
            }
        }

        Button {
            id: buttonNewMachine6
            x: 1300
            y: 430
            width: 550
            height: 375
            icon.width: 537
            icon.source: "images/New_Machine_Button.png"
            icon.height: 360
            icon.color: "#007a2828"
            flat: true
            Connections {
                target: buttonNewMachine6
                onClicked: stackView.push("Basic_OS_Selection.qml")
            }
        }

        Image {
            id: oS_Selector_Background
            x: 74
            y: 36
            source: "images/OS_Selector_Background.png"
            fillMode: Image.PreserveAspectFit

            TextInput {
                id: textInput
                x: 133
                y: 22
                width: 284
                height: 52
                color: "#f2f8f9"
                text: qsTr("Mi Máquina")
                font.pixelSize: 30
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                selectionColor: "#565151"
            }

            Text {
                id: text1
                x: 29
                y: 307
                width: 241
                height: 39
                color: "#f2f8f9"
                text: qsTr("Bodhi Linux")
                font.pixelSize: 28
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignBottom
            }

            Text {
                id: text2
                x: 276
                y: 307
                width: 235
                height: 39
                color: "#f2f8f9"
                text: qsTr("700 Cr/hora")
                font.pixelSize: 28
                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignBottom
            }

            Button {
                id: button
                x: 458
                y: 21
                width: 65
                height: 65
                icon.height: 60
                icon.width: 60
                icon.color: "#f2f8f9"
                icon.source: "images/Menu_Button.png"
                flat: true

                Connections {
                    target: button
                    function onClicked() { stackView.push("Contextual_Menu.qml") }
                }
            }

            Button {
                id: button1
                x: 125
                y: 101
                width: 300
                height: 200
                icon.height: 200
                icon.width: 200
                icon.color: "#00000000"
                icon.source: "images/Bodhi_Linux_Icon.png"
                flat: true

                Connections {
                    target: button1
                    function onClicked() { console.log("Connecting...");  myMachine.mi_maquina_function()  }
                }
            }

            Text {
                id: text3
                x: 154
                y: 66
                width: 243
                height: 39
                color: "#e1cfb2b2"
                text: qsTr("Creado")
                font.pixelSize: 22
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignTop
            }
        }

    }
}
