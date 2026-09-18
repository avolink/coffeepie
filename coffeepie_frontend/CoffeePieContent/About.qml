import QtQuick
import QtQuick.Controls

Item {
    id: aboutPage
    anchors.fill: parent

    Rectangle {
        id: background
        anchors.fill: parent
        color: "#323030"

        Button {
            id: buttonClose
            x: parent.width - 120
            y: 10
            width: 100
            height: 80
            icon.width: 70
            icon.source: "images/Close_Button.png"
            icon.height: 70
            icon.color: "#f2f8f9"
            flat: true
            onClicked: stackView.clear()
        }

        Text {
            id: labelTitle
            anchors.horizontalCenter: parent.horizontalCenter
            y: 50
            width: 800
            height: 60
            color: "#f2f8f9"
            text: "Coffee Pie\u00AE"
            font.pixelSize: 48
            horizontalAlignment: Text.AlignHCenter
        }

        Text {
            id: labelSubtitle
            anchors.horizontalCenter: parent.horizontalCenter
            y: 120
            width: 800
            height: 40
            color: "#eaeaea"
            text: tr.tr("Acerca de Coffee Pie\u00AE")
            font.pixelSize: 28
            horizontalAlignment: Text.AlignHCenter
        }

        ScrollView {
            id: scrollView
            anchors.horizontalCenter: parent.horizontalCenter
            y: 180
            width: 1200
            height: parent.height - 260

            Text {
                id: txtAboutContent
                width: 1160
                color: "#f2f8f9"
                font.pixelSize: 18
                wrapMode: Text.WordWrap
                text: tr.tr("Coffee Pie\u00AE es un ecosistema tecnol\u00F3gico abierto que provee un servicio de c\u00F3mputo de prop\u00F3sito general, como un \"caf\u00E9 internet\" o \"cibercaf\u00E9\", pero desde la comodidad de tu hogar, oficina o espacio p\u00FAblico con acceso a internet, con capacidades flexibles, sin altos costos, sin ataduras, sin mantenimiento, sin calor ni ruido significativo, y sin generar basura electr\u00F3nica.\n\nBasado en el sistema patentado QFDM (Quantized Fractional Distribution and Management System), Patente NC2025/0012723, Coffee Pie\u00AE democratiza el poder de c\u00F3mputo y contribuye a la erradicaci\u00F3n de la basura electr\u00F3nica global.\n\nEspecificaciones T\u00E9cnicas Porci\u00F3n Coffee Pie\u00AE:\n\nPWR: 1 Wh\nCPU: 1 vCore\nRAM: 1 GB\nSSD: 8 GB\nNET: 8 Mbps\nHDD: 125 GB\nGPU: 125 MB\nRES: 15 vMPX/s\nIA: 3 TOPS (INT8)\n\nMisi\u00F3n: Democratizar el poder de c\u00F3mputo y erradicar la basura electr\u00F3nica global.\n\nVisi\u00F3n: Ser el est\u00E1ndar global de c\u00F3mputo sostenible y accesible para el 2035.\n\nwww.coffeepie.co")
            }
        }
    }
}
