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
            id: lblOrganization
            x: 14
            y: 170
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Organización (Nombre Comercial)")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter

            Text {
                id: lblTechEmail
                x: 0
                y: 465
                width: 545
                height: 50
                color: "#ffffff"
                text: qsTr("Correo Electrónico Sistemas")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
                onFocusChanged: if (focus) selectAll()
            }

            Text {
                id: lblTechContact
                x: 0
                y: 522
                width: 545
                height: 50
                color: "#ffffff"
                text: qsTr("Nombre del Contacto")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: lblTechContactNumber
                x: 0
                y: 581
                width: 537
                height: 50
                color: "#ffffff"
                text: qsTr("Número del Contacto")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: lblWebsite
                x: 0
                y: 638
                width: 545
                height: 50
                color: "#ffffff"
                text: qsTr("Sitio Web (URL)")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: lblDomain
                x: 0
                y: 696
                width: 545
                height: 50
                color: "#ffffff"
                text: qsTr("Dominio")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }
        }

        Text {
            id: lblLegalName
            x: 14
            y: 228
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Razón Social (Nombre Fiscal)")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblLegalId
            x: 14
            y: 286
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Identificación Tributaria (NIT)")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblIvoiceEmail
            x: 14
            y: 345
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Correo Electrónico")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblContactName
            x: 14
            y: 401
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Nombre de Contacto")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblContactNumber
            x: 14
            y: 460
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Número de Contacto")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblLegalAddress
            x: 14
            y: 517
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Dirección Fiscal (Facturación)")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblPhysicalAddress
            x: 14
            y: 922
            width: 545
            height: 50
            color: "#ffffff"
            text: qsTr("Dirección Física (Instalaciones)")
            font.pixelSize: 36
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblInvoiceContact
            x: 144
            y: 101
            width: 1637
            height: 60
            color: "#ffffff"
            text: qsTr("Contacto Facturación (Contabilidad)")
            font.pixelSize: 50
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: lblMyAccount
            x: 169
            y: 29
            width: 1605
            height: 62
            color: "#ffffff"
            text: qsTr("Mi Cuenta")
            font.pixelSize: 64
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        Text {
            id: txtOrganization3
            x: 115
            y: 577
            width: 1691
            height: 50
            color: "#ffffff"
            text: qsTr("Contacto Sistemas (Tech/IT)")
            font.pixelSize: 50
            horizontalAlignment: Text.AlignHCenter
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
        id: buttonSaveChanges
        x: 744
        y: 999
        width: 435
        height: 63
        text: qsTr("Guardar Cambios")
        icon.width: 30
        font.pointSize: 20
        flat: false
        Connections {
            target: buttonSaveChanges
            function onClicked() { console.log("clicked") }
        }
    }

    TextField {
        id: inputFieldOrganization
        x: 565
        y: 168
        width: 789
        height: 54
        visible: true
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Organización")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldOrganization
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldLegalName
        x: 565
        y: 226
        width: 789
        height: 54
        visible: true
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Razón Social")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldLegalName
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldLegalId
        x: 565
        y: 284
        width: 789
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Identificación Tributaria")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldLegalId
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldInvoiceEmail
        x: 565
        y: 342
        width: 789
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Correo Electrónico")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldInvoiceEmail
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldInvoiceContactName
        x: 565
        y: 401
        width: 789
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Nombre de Contacto")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldInvoiceContactName
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldContactNumber
        x: 565
        y: 459
        width: 789
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Número de Contacto")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldContactNumber
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldLegalAddress
        x: 565
        y: 518
        width: 790
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Dirección Fiscal")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldLegalAddress
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldTechContactEmail
        x: 566
        y: 633
        width: 790
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Correo Electrónico Sistemas")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldTechContactEmail
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldTechContactName
        x: 566
        y: 691
        width: 790
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Nombre de Contacto")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldTechContactName
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldTechContactNumber
        x: 566
        y: 749
        width: 790
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Número de Contacto")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldTechContactNumber
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldWebsite
        x: 566
        y: 807
        width: 790
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Sitio Web")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldWebsite
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldDomain
        x: 566
        y: 865
        width: 790
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Dominio")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldDomain
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }

    TextField {
        id: inputFieldPhysicalAddress
        x: 566
        y: 923
        width: 790
        height: 54
        visible: true
        text: ""
        selectionColor: "#908f8f"
        selectedTextColor: "#ffffff"
        placeholderText: qsTr("Dirección Física")
        inputMask: ""
        font.pointSize: 20
        Connections {
            target: inputFieldPhysicalAddress
        } Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: flat
        }
    }
}
