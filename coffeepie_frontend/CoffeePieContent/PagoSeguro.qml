import QtQuick
import QtQuick.Controls

Item {
    id: root
    width: 1920
    height: 1080

    property string selectedPackage: "SMALL"
    property int amount: 10000
    property int credits: 10000

    Rectangle {
        id: mainRect
        x: 0
        y: 0
        width: 1920
        height: 1080
        color: "#908f8f"

        Button {
            id: buttonClose
            x: 1807
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
                onClicked: stackView.clear()
            }
        }

        Text {
            id: lblTitle
            x: 0
            y: 30
            width: 1920
            height: 56
            color: "#ffffff"
            text: tr.tr("PAGO SEGURO")
            font.pixelSize: 44
            horizontalAlignment: Text.AlignHCenter
        }

        Text {
            id: lblSubtitle
            x: 0
            y: 90
            width: 1920
            height: 36
            color: "#cccccc"
            text: tr.tr("Escanea el código QR con tu app Bancolombia")
            font.pixelSize: 24
            horizontalAlignment: Text.AlignHCenter
        }

        Row {
            x: 150
            y: 160
            spacing: 30

            Rectangle {
                width: 500
                height: 350
                color: "#ffffff"
                radius: 12
                Rectangle {
                    anchors.centerIn: parent
                    width: 220
                    height: 220
                    color: "#ffffff"
                    border.color: "#999999"
                    border.width: 2
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 20
                    text: tr.tr("Paquete Pequeño\n10.000 Créditos")
                    font.pixelSize: 18
                    horizontalAlignment: Text.AlignHCenter
                    color: "#333333"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        selectedPackage = "SMALL"
                        amount = 10000
                        credits = 10000
                    }
                }
            }

            Rectangle {
                width: 500
                height: 350
                color: "#ffffff"
                radius: 12
                border.color: "#c18b44"
                border.width: 4
                Rectangle {
                    anchors.centerIn: parent
                    width: 220
                    height: 220
                    color: "#ffffff"
                    border.color: "#999999"
                    border.width: 2
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 20
                    text: tr.tr("Paquete Mediano\n500.000 Créditos")
                    font.pixelSize: 18
                    horizontalAlignment: Text.AlignHCenter
                    color: "#333333"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: 12
                    text: tr.tr("MÁS POPULAR")
                    font.pixelSize: 14
                    font.bold: true
                    color: "#ffffff"
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -6
                        color: "#c18b44"
                        z: -1
                        radius: 8
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        selectedPackage = "MEDIUM"
                        amount = 50000
                        credits = 500000
                    }
                }
            }

            Rectangle {
                width: 500
                height: 350
                color: "#ffffff"
                radius: 12
                Rectangle {
                    anchors.centerIn: parent
                    width: 220
                    height: 220
                    color: "#ffffff"
                    border.color: "#999999"
                    border.width: 2
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 20
                    text: tr.tr("Paquete Grande\n6.000.000 Créditos")
                    font.pixelSize: 18
                    horizontalAlignment: Text.AlignHCenter
                    color: "#333333"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        selectedPackage = "LARGE"
                        amount = 300000
                        credits = 6000000
                    }
                }
            }
        }

        Rectangle {
            x: 260
            y: 560
            width: 1400
            height: 260
            color: "#ffffff"
            radius: 8

            Text {
                id: lblTransferInfo
                x: 30
                y: 20
                text: tr.tr("Datos de Transferencia Bancaria")
                font.pixelSize: 24
                font.bold: true
                color: "#000000"
            }

            Column {
                x: 30
                y: 70
                spacing: 10
                Repeater {
                    model: [
                        { label: "Banco:", value: "Bancolombia" },
                        { label: "Tipo de Cuenta:", value: "Cuenta Corriente" },
                        { label: "Titular:", value: "Coffee Pie S.A.S. BIC" },
                        { label: "NIT:", value: "901.xxx.xxx-x" },
                        { label: "Referencia:", value: "CP-" + selectedPackage }
                    ]
                    Row {
                        spacing: 10
                        Text {
                            width: 180
                            text: modelData.label
                            font.pixelSize: 18
                            color: "#555555"
                            horizontalAlignment: Text.AlignRight
                        }
                        Text {
                            text: modelData.value
                            font.pixelSize: 18
                            font.bold: true
                            color: "#000000"
                        }
                    }
                }
            }
        }

        Text {
            id: lblInstructions
            x: 260
            y: 850
            width: 1400
            text: tr.tr("Instrucciones: 1. Abre la app Bancolombia  2. Toca 'Pagar con QR'  3. Escanea el código del paquete deseado  4. Confirma el pago  5. Tus créditos se acreditarán automáticamente")
            font.pixelSize: 16
            color: "#cccccc"
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }

        Button {
            id: buttonConfirmManual
            x: 760
            y: 920
            width: 400
            height: 60
            text: tr.tr("Ya realicé el pago")
            font.pointSize: 18
            Connections {
                target: buttonConfirmManual
                onClicked: api.purchasePackage(selectedPackage)
            }
        }
    }
}
