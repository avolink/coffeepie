import QtQuick
import QtQuick.Controls

Item {
    id: root
    width: 1920
    height: 1080

    Rectangle {
        id: mainMenu
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

        Connections {
            target: api
            function onOrchestratorsLoaded(data) {
                txtOrchFallback.text = data
            }
        }

        Text {
            id: lblKeepAdvancedMode
            x: 39
            y: 137
            width: 545
            height: 50
            color: "#ffffff"
            text: tr.tr("Iniciar en Modo Avanzado")
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
            text: tr.tr("Configuración Avanzada")
            font.pixelSize: 54
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblUpscaling
            x: 39
            y: 246
            width: 545
            height: 50
            color: "#ffffff"
            text: tr.tr("Upscaling")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }
        
        Text {
            id: lblRenderization
            x: 39
            y: 302
            width: 545
            height: 50
            color: "#ffffff"
            text: tr.tr("Renderization")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }
        
        Text {
            id: lblRasterization
            x: 39
            y: 359
            width: 545
            height: 50
            color: "#ffffff"
            text: tr.tr("Rasterization")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }
        
        Text {
            id: lblShaders
            x: 39
            y: 416
            width: 545
            height: 50
            color: "#ffffff"
            text: tr.tr("Shaders")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }
        
        Text {
            id: lblAntialiasing
            x: 39
            y: 472
            width: 545
            height: 50
            color: "#ffffff"
            text: tr.tr("Anti-aliasing")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblMotionBlur
            x: 39
            y: 525
            width: 545
            height: 50
            color: "#ffffff"
            text: tr.tr("Motion Blur")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblUSBIP
            x: 39
            y: 191
            width: 545
            height: 50
            color: "#ffffff"
            text: tr.tr("USB/IP")
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
        text: tr.tr("Cargar Valores Predeterminados")
        icon.width: 30
        font.pointSize: 20
        flat: false

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
        text: tr.tr("Guardar Cambios")
        icon.width: 30
        font.pointSize: 20
        flat: false
        Connections {
            target: buttonSaveChanges
            onClicked: console.log("clicked")
        }
    }

    ComboBox {
        id: selectStartInAdvancedMode
        x: 588
        y: 136
        width: 700
        height: 50
        model: ["False","True"]
        font.pointSize: 20
        flat: false
        editable: false
    }

    ComboBox {
        id: selectUSBIP
        x: 588
        y: 192
        width: 700
        height: 50
        model: ["On","Off"]
        font.pointSize: 20
        flat: false
        editable: false
    }

    ComboBox {
        id: selectUpscaling
        x: 588
        y: 248
        width: 700
        height: 50
        model: ["Auto DLSS (Deep Learning Super Sampling)","FSR4","FSR3.1","FSR3.0","FSR2.0","FR1.0"]
        font.pointSize: 20
        flat: false
        editable: false
    }

    ComboBox {
        id: selectRenderization
        x: 588
        y: 304
        width: 700
        height: 50
        model: ["x1.0 (Automatic)","x5.0","x4.0","x3.0","x2.0","x0.75","x0.5","x0.25"]
        font.pointSize: 20
        flat: false
        editable: false
    }

    ComboBox {
        id: selectRasterization
        x: 588
        y: 360
        width: 700
        height: 50
        model: ["Automatic","Triangle Rasterization","Line Rasterization Aliased","Line Rasterization Antialiased","Point Rasterization"]
        font.pointSize: 20
        flat: false
        editable: false
    }

    ComboBox {
        id: selectShaders
        x: 588
        y: 416
        width: 700
        height: 50
        model: ["Automatic","OpenGL","DirectX"]
        font.pointSize: 20
        flat: false
        editable: false
    }

    ComboBox {
        id: selectAntialiasing
        x: 588
        y: 472
        width: 700
        height: 50
        model: ["TAA (Temporal)","MSAA (Multisample)","SSAA (Supersampling)","FXAA (Fast Approximate)","MLAA (Morphological)","SMAA (Enhanced Subpixel Morphological)"]
        font.pointSize: 20
        flat: false
        editable: false
    }

    ComboBox {
        id: selectMotionBlur
        x: 588
        y: 528
        width: 700
        height: 50
        model: ["Off","On"]
        font.pointSize: 20
        flat: false
        editable: false
    }

    Text {
        id: lblNetworkConfig
        x: 39
        y: 620
        width: 545
        height: 50
        color: "#ffffff"
        text: tr.tr("Red y Conectividad")
        font.pixelSize: 36
        horizontalAlignment: Text.AlignLeft
        verticalAlignment: Text.AlignVCenter
    }

    Text {
        id: lblNetworkTier
        x: 39
        y: 680
        width: 545
        height: 50
        color: "#999999"
        text: tr.tr("Nivel de Red")
        font.pixelSize: 28
        horizontalAlignment: Text.AlignLeft
        verticalAlignment: Text.AlignVCenter
    }

    Text {
        id: txtNetworkTier
        x: 588
        y: 680
        width: 700
        height: 50
        color: "#ffffff"
        text: api.getNetworkTierLabel()
        font.pixelSize: 24
        horizontalAlignment: Text.AlignLeft
        verticalAlignment: Text.AlignVCenter
    }

    Text {
        id: lblOrchFallback
        x: 39
        y: 740
        width: 545
        height: 50
        color: "#999999"
        text: tr.tr("Orquestadores")
        font.pixelSize: 28
        horizontalAlignment: Text.AlignLeft
        verticalAlignment: Text.AlignVCenter
    }

    TextArea {
        id: txtOrchFallback
        x: 588
        y: 740
        width: 700
        height: 120
        color: "#ffffff"
        text: api.orchestratorsJson
        font.pixelSize: 16
        readOnly: true
        background: Rectangle { color: "#555555"; radius: 4 }
    }

    Button {
        id: buttonFetchOrch
        x: 1308
        y: 740
        width: 120
        height: 40
        text: tr.tr("Actualizar")
        font.pointSize: 14
        Connections {
            target: buttonFetchOrch
            onClicked: api.fetchOrchestrators()
        }
    }

    Button {
        id: buttonFetchTurn
        x: 588
        y: 870
        width: 200
        height: 40
        text: tr.tr("Obtener credenciales TURN")
        font.pointSize: 14
        Connections {
            target: buttonFetchTurn
            onClicked: api.fetchTurnCredentials()
        }
    }

}
