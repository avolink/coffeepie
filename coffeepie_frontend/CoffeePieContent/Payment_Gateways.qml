import QtQuick
import QtQuick.Controls

Item {
    id: root
    width: 1920
    height: 1080



    MouseArea {
        id: mouseArea
        x: 0
        y: 0
        width: 1920
        height: 1080

        Connections {
            target: mouseArea
            onClicked: stackView.clear()
        }
    }

    Connections {
        target: api
        function onPurchaseCompleted(result) {
            purchaseStatus.text = "Compra exitosa"
            purchaseStatus.color = "#00ff00"
            purchaseStatus.visible = true
            timerHideStatus.start()
        }
        function onPurchaseFailed(error) {
            purchaseStatus.text = "Error: " + error
            purchaseStatus.color = "#ff6666"
            purchaseStatus.visible = true
            timerHideStatus.start()
        }
    }

    Timer {
        id: timerHideStatus
        interval: 5000
        onTriggered: purchaseStatus.visible = false
    }

    Rectangle {
        id: mainMenu
        x: 235
        y: 110
        width: 1450
        height: 860
        visible: true
        color: "#ffffff"

        Text {
            id: _text
            x: 145
            y: 30
            width: 1170
            height: 56
            text: tr.tr("PASARELAS DE PAGO")
            font.pixelSize: 44
            horizontalAlignment: Text.AlignHCenter
            font.bold: false
        }

        Text {
            id: purchaseStatus
            x: 145
            y: 90
            width: 1170
            height: 30
            font.pixelSize: 20
            horizontalAlignment: Text.AlignHCenter
            visible: false
        }

        MouseArea {
            id: mouseAreaINeutral
            x: 0
            y: 0
            width: 1450
            height: 860

            Connections {
                target: mouseAreaINeutral
                onClicked: console.log("clicked")
            }
        }
        Button {
            id: buttonClose
            x: 1346
            y: 8
            width: 100
            height: 92
            icon.width: 80
            icon.source: "images/Close_Button.png"
            icon.height: 80
            icon.color: "#000000"
            flat: true
            Connections {
                target: buttonClose
                onClicked: stackView.clear()
            }
        }
    }

    Image {
        id: nequi_Logo
        x: 757
        y: 534
        width: 426
        height: 306
        source: "images/Payment_Gateways/Nequi_Logo.png"
        fillMode: Image.PreserveAspectFit

        MouseArea {
            id: mouseArea5
            x: 35
            y: 22
            width: 357
            height: 261

            Connections {
                target: mouseArea5
                onClicked: stackView.push("PagoSeguro.qml")
            }
        }
    }

    Image {
        id: payU_Logo
        x: 361
        y: 237
        width: 408
        height: 304
        source: "images/Payment_Gateways/PayU_Logo.png"
        fillMode: Image.PreserveAspectFit

        MouseArea {
            id: mouseArea1
            x: 23
            y: 21
            width: 366
            height: 263

            Connections {
                target: mouseArea1
                onClicked: stackView.push("PagoSeguro.qml")
            }
        }
    }

    Image {
        id: placeToPay_Logo
        x: 360
        y: 534
        width: 415
        height: 306
        source: "images/Payment_Gateways/PlaceToPay_Logo.png"
        fillMode: Image.PreserveAspectFit

        MouseArea {
            id: mouseArea4
            x: 22
            y: 20
            width: 362
            height: 261

            Connections {
                target: mouseArea4
                onClicked: stackView.push("PagoSeguro.qml")
            }
        }
    }

    Image {
        id: ePayco_Logo
        x: 1161
        y: 237
        width: 422
        height: 304
        source: "images/Payment_Gateways/ePayco_Logo.png"
        fillMode: Image.PreserveAspectFit

        MouseArea {
            id: mouseArea3
            x: 38
            y: 26
            width: 349
            height: 255

            Connections {
                target: mouseArea3
                onClicked: stackView.push("PagoSeguro.qml")
            }
        }
    }


    Image {
        id: mercadoPago
        x: 1168
        y: 541
        width: 415
        height: 297
        source: "images/Payment_Gateways/MercadoPago.png"
        fillMode: Image.PreserveAspectFit

        MouseArea {
            id: mouseArea6
            x: 26
            y: 18
            width: 357
            height: 255

            Connections {
                target: mouseArea6
                onClicked: stackView.push("PagoSeguro.qml")
            }
        }
    }

    Image {
        id: pSE_Logo
        x: 768
        y: 237
        width: 404
        height: 304
        source: "images/Payment_Gateways/PSE_Logo.png"
        fillMode: Image.PreserveAspectFit

        MouseArea {
            id: mouseArea2
            x: 25
            y: 26
            width: 358
            height: 258

            Connections {
                target: mouseArea2
                onClicked: stackView.push("PagoSeguro.qml")
            }
        }
    }

    RoundButton {
        id: roundButton
        x: 884
        y: 780
        width: 152
        height: 156
        icon.width: 160
        icon.source: "images/Honey_Button.png"
        icon.height: 160
        icon.color: "#007a2828"
        flat: true
    }
}
