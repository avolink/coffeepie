import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    width: 1920
    height: 1080

    Rectangle {
        id: basicCofig
        x: 0
        y: 0
        width: 1920
        height: 1080
        visible: true
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
            id: lblInterfaceLanguage
            x: 8
            y: 121
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Lenguaje de Interfaz")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter

            Text {
                id: txtOrganization4
                x: 0
                y: 620
                width: 545
                height: 50
                color: "#ffffff"
                text: qsTr("Dirección MAC")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: txtLegalName7
                x: 0
                y: 569
                width: 545
                height: 50
                color: "#ffffff"
                text: qsTr("Proveedor de Internet (ISP)")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: txtLegalName8
                x: 0
                y: 672
                width: 537
                height: 50
                color: "#ffffff"
                text: qsTr("Dirección IPv4")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: txtLegalName9
                x: 0
                y: 728
                width: 545
                height: 50
                color: "#ffffff"
                text: qsTr("Dirección IPv6")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: txtLegalName10
                x: 0
                y: 784
                width: 545
                height: 50
                color: "#ffffff"
                text: qsTr("Máscara de Subred")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: txtLegalName11
                x: 0
                y: 834
                width: 545
                height: 50
                color: "#ffffff"
                text: qsTr("Puerta de Enlace Predeterminada")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }
        }

        Text {
            id: lblDefaultConection
            x: 8
            y: 174
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Conexión Predeterminada")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblDefaultCodec
            x: 8
            y: 229
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Codec Predeterminado")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblDefaultResolution
            x: 8
            y: 285
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Resolución Predeterminada")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblDefaulBitrate
            x: 8
            y: 341
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Bitrate Predeterminado")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblDefaultRecurrence
            x: 8
            y: 397
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Recurrencia Predeterminada")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblDefaultMachineState
            x: 8
            y: 453
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Estado Predeterminado Máquina")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblDataSync
            x: 8
            y: 509
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Sincronización de Datos")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblBasicConfig
            x: 155
            y: 29
            width: 1646
            height: 62
            color: "#ffffff"
            text: qsTr("Configuración Básica")
            font.pixelSize: 54
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblNetworkConfig
            x: 115
            y: 622
            width: 1691
            height: 50
            color: "#ffffff"
            text: qsTr("Configuración de Red")
            font.pixelSize: 54
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblBackupsSync
            x: 8
            y: 564
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Sincronización de Respaldos")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        ComboBox {
            id: selectInterfaceLanguage
            x: 560
            y: 116
            width: 700
            height: 50
            font.pointSize: 20
            flat: false
            editable: false
            model: ["Spanish","English","Portuguese","French"]
        }

        ComboBox {
            id: selectDefaultConection
            x: 560
            y: 172
            width: 700
            height: 50
            font.pointSize: 20
            editable: false
            flat: false
            model: ["Auto","Optical Fiber","WiFi","5G","4G"]
        }

        ComboBox {
            id: selectDefaultCodec
            x: 560
            y: 228
            width: 700
            height: 50
            font.pointSize: 20
            editable: false
            flat: false
            model: ["Auto","AV1","H.265","H.264","MPEG-2","ACC"]
        }

        ComboBox {
            id: selectDefaultResolution
            x: 560
            y: 284
            width: 700
            height: 50
            font.pointSize: 20
            editable: false
            flat: false
            model: ["Auto","8K (7680 x 4320 px)","4K (3840 x 2160 px)","2K (2560 x 1440 px)","FHD (1920 x 1080 px)", "HD (1280 x 720 px)","SD (854 x 480 px)","LD (640 x 360 px)","VHS (426 x 240 px)","Low Res (256 x 144 px)"]
        }

        ComboBox {
            id: selectDefaulBitrate
            x: 560
            y: 340
            width: 700
            height: 50
            font.pointSize: 20
            editable: false
            flat: false
            model: ["Auto","100","90","80","70","60","50","40","30","20","10","5","2.5","1"]
        }

        ComboBox {
            id: selectlblDefaultRecurrence
            x: 560
            y: 396
            width: 700
            height: 50
            font.pointSize: 20
            editable: false
            flat: false
            model: ["Hourly","Monthly","Yearly"]
        }

        ComboBox {
            id: selectDefaultMachineState
            x: 560
            y: 452
            width: 700
            height: 50
            font.pointSize: 20
            editable: false
            flat: false
            model: ["Off","On"]
        }

        ComboBox {
            id: selectDataSync
            x: 560
            y: 508
            width: 700
            height: 50
            font.pointSize: 20
            editable: false
            flat: false
            model: ["Auto","Manual"]
        }

        ComboBox {
            id: selectBackupsSync
            x: 560
            y: 564
            width: 700
            height: 50
            font.pointSize: 20
            editable: false
            flat: false
            model: ["Auto","Manual"]
        }

        Button {
            id: buttonAdvancedConfig
            x: 1485
            y: 1017
            width: 435
            height: 63
            text: qsTr("Configuración Avanzada")
            font.pointSize: 20
            icon.width: 30
            flat: false

            Connections {
                target: buttonAdvancedConfig
                onClicked: stackView.push("Config_Advanced.qml", StackView.Immediate)
            }
        }

        TextEdit {
            id: textEdit8
            x: 559
            y: 740
            width: 793
            height: 50
            color: "#ffffff"
            text: qsTr("40-B0-76-7C-3D-F6")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        TextEdit {
            id: textEdit9
            x: 559
            y: 689
            width: 793
            height: 50
            color: "#ffffff"
            text: qsTr("tigoune.com.co")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        TextEdit {
            id: textEdit10
            x: 559
            y: 792
            width: 793
            height: 50
            color: "#ffffff"
            text: qsTr("192.168.1.255")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        TextEdit {
            id: textEdit11
            x: 559
            y: 847
            width: 793
            height: 50
            color: "#ffffff"
            text: qsTr("2800:e2:b27f:fba9:5737:443f:9345:6774")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        TextEdit {
            id: textEdit12
            x: 559
            y: 904
            width: 793
            height: 50
            color: "#ffffff"
            text: qsTr("255.255.255.0")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        TextEdit {
            id: textEdit13
            x: 559
            y: 955
            width: 793
            height: 50
            color: "#ffffff"
            text: qsTr("fe80::4632:c8ff:feee:bf47%14")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }
    }

    Button {
        id: buttonHelp
        x: 33
        y: 33
        width: 120
        height: 80
        icon.width: 100
        icon.source: "images/Support_Button.png"
        icon.height: 100
        icon.color: "#eaeaea"
        flat: true

        Connections {
            target: buttonHelp
            function onClicked() { stackView.push("About.qml") }
        }
    }

    Button {
        id: buttonLoadDefaults
        x: 0
        y: 1017
        width: 435
        height: 63
        text: qsTr("Cargar Valores Predeterminados")
        icon.width: 30
        font.pointSize: 20
        flat: false
        Connections {
            target: buttonLoadDefaults
            onClicked: stackView.push("Config_Advanced.qml")
        }

        Connections {
            target: buttonLoadDefaults
            onClicked: console.log("clicked")
        }
    }

    Button {
        id: buttonSaveChanges
        x: 743
        y: 1017
        width: 435
        height: 63
        text: qsTr("Guardar Cambios")
        icon.width: 30
        font.pointSize: 20
        flat: false
        Connections {
            target: buttonSaveChanges
            onClicked: console.log("clicked")
        }

        Connections {
            target: buttonSaveChanges
            onClicked: console.log("clicked")
        }
    }
}
