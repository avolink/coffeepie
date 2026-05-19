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

        Text {
            id: lblAccountStatus
            x: 14
            y: 120
            width: 1342
            height: 40
            color: "#00ff00"
            text: ""
            font.pixelSize: 24
            horizontalAlignment: Text.AlignHCenter
            visible: false
        }

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
            function onAccountSaved(message) {
                lblAccountStatus.text = message
                lblAccountStatus.color = "#00ff00"
                lblAccountStatus.visible = true
                timerHide.interval = 5000
                timerHide.start()
            }
            function onAccountError(error) {
                lblAccountStatus.text = error
                lblAccountStatus.color = "#ff6666"
                lblAccountStatus.visible = true
                timerHide.interval = 5000
                timerHide.start()
            }
        }

        Timer {
            id: timerHide
            interval: 5000
            onTriggered: lblAccountStatus.visible = false
        }

        Text {
            id: lblOrganization
            x: 14
            y: 170
            width: 545
            height: 50
            color: "#ffffff"
            text: tr.tr("Organización (Nombre Comercial)")
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
                text: tr.tr("Correo Electrónico Sistemas")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: lblTechContact
                x: 0
                y: 522
                width: 545
                height: 50
                color: "#ffffff"
                text: tr.tr("Nombre del Contacto")
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
                text: tr.tr("Número del Contacto")
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
                text: tr.tr("Sitio Web (URL)")
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
                text: tr.tr("Dominio")
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
            text: tr.tr("Razón Social (Nombre Fiscal)")
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
            text: tr.tr("Identificación Tributaria (NIT)")
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
            text: tr.tr("Correo Electrónico")
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
            text: tr.tr("Nombre de Contacto")
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
            text: tr.tr("Número de Contacto")
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
            text: tr.tr("Dirección Fiscal (Facturación)")
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
            text: tr.tr("Dirección Física (Instalaciones)")
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
            text: tr.tr("Contacto Facturación (Contabilidad)")
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
            text: tr.tr("Mi Cuenta")
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
            text: tr.tr("Contacto Sistemas (Tech/IT)")
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
        text: tr.tr("Guardar Cambios")
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
        placeholderText: tr.tr("Organización")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Razón Social")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Identificación Tributaria")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Correo Electrónico")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Nombre de Contacto")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Número de Contacto")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Dirección Fiscal")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Correo Electrónico Sistemas")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Nombre de Contacto")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Número de Contacto")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Sitio Web")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Dominio")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
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
        placeholderText: tr.tr("Dirección Física")
        inputMask: ""
        font.pointSize: 20
        Keys.onReturnPressed: {
            nextItemInFocusChain().forceActiveFocus()
        }
        background: Rectangle {
            color: "transparent"
        }
    }
}
