import QtQuick 2.15
import QtQuick.Controls 2.15

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

        Text {
            id: lblKeepAdvancedMode
            x: 39
            y: 137
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Iniciar en Modo Avanzado")
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
            text: qsTr("Configuración Avanzada")
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
            text: qsTr("Upscaling")
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
            text: qsTr("Renderization")
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
            text: qsTr("Rasterization")
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
            text: qsTr("Shaders")
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
            text: qsTr("Anti-aliasing")
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
            text: qsTr("Motion Blur")
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
            text: qsTr("USB/IP")
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

}
