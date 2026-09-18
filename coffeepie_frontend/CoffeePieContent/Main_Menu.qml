import QtQuick   2.15
import QtQuick.Controls  2.15


Item {
    id: root
    width: 1920
    height: 1080
     z: 2
    Rectangle {
        id: mainMenu
        x: 1420
        y: 0
        width: 500
        height: 1080
        visible: true
        color: "#908f8f"
        Button {
            id: buttonClose
            x: 387
            y: 16
            width: 100
            height: 92
            icon.width: 80
            icon.source: "images/Close_Button.png"
            icon.height: 80
            icon.color: "#007a2828"
            flat: true
            Connections {
                target: buttonClose
                onClicked: stackView.clear("Main_Menu.qml", StackView.Immediate)
            }
        }

        Button {
            id: buttonRecharge
            x: 25
            y: 36
            width: 350
            height: 53
            transformOrigin: Item.Center
            icon.color: "#eaeaea"
            icon.cache: true
            font.pointSize: 24
            font.bold: true
            flat: true
            palette.buttonText: "white"

            Connections {
                target: buttonRecharge
                onClicked: stackView.push("Payment_Gateways.qml", StackView.Immediate)
            }

            Text {
                id: txtRecharge
                x: 16
                y: 0
                width: 334
                height: 53
                color: "#ffffff"
                text: qsTr("Recargar Saldo")
                font.pixelSize: 30
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
                styleColor: "#ffffff"
                font.bold: true
            }
        }

        Button {
            id: buttonMyAccount
            x: 25
            y: 121
            width: 350
            height: 53
            icon.color: "#eaeaea"
            icon.cache: true
            font.pointSize: 24
            font.bold: true
            flat: true
            palette.buttonText: "white"

            Text {
                id: txtMyAccount
                x: 16
                y: 0
                width: 316
                height: 53
                color: "#ffffff"
                text: qsTr("Mi Cuenta")
                font.pixelSize: 30
                verticalAlignment: Text.AlignVCenter
                font.bold: true
            }

            Connections {
                target: buttonMyAccount
                onClicked: stackView.push("My_Account.qml")
            }
        }

        Button {
            id: buttonConfig
            x: 25
            y: 208
            width: 350
            height: 53
            icon.color: "#eaeaea"
            icon.cache: true
            font.pointSize: 24
            font.bold: true
            flat: true
            palette.buttonText: "white"

            Text {
                id: txtConfig
                x: 16
                y: 0
                width: 308
                height: 53
                color: "#ffffff"
                text: qsTr("Configuración")
                font.pixelSize: 30
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
                font.bold: true
            }

            Connections {
                target: buttonConfig
                onClicked: stackView.push("Config.qml")
            }
        }

        Button {
            id: buttonLogout
            x: 25
            y: 294
            width: 323
            height: 53
            icon.color: "#eaeaea"
            icon.cache: true
            font.pointSize: 24
            font.bold: true
            flat: true
            palette.buttonText: "white"
            Connections {
                target: buttonLogout
                onClicked: Qt.quit()
            }

            Text {
                id: txtLogout
                x: 15
                y: 0
                width: 256
                height: 53
                color: "#ffffff"
                text: qsTr("Cerrar Sesión")
                font.pixelSize: 30
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
                font.bold: true
            }
        }

        RoundButton {
            id: roundButtonTechSupport
            x: 193
            y: 941
            width: 114
            height: 114
            text: "+"
            icon.height: 200
            icon.width: 200
            icon.source: "images/Tech_Support.png"
            icon.color: "#00000000"

            Connections {
                target: roundButtonTechSupport
                function onClicked() { console.log("clicked") }
            }
        }
    }

    MouseArea {
        id: mouseArea
        x: 0
        y: 0
        width: 1423
        height: 1080

        Connections {
            target: mouseArea
            onClicked: stackView.clear()
        }
    }
}
