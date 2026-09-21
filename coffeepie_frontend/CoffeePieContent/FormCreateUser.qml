import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: formRoot
    width: 400
    height: 600

    property alias name: nameField.text
    property alias email: emailField.text
    property alias type: typeField.text
    property alias companyID: companyIDField.text
    property alias age: ageField.text
    property alias city: cityField.text
    property alias occupation: occupationField.text
    property alias portions: portionsField.text
    property alias password: passwordField.text

    Column {
        spacing: 10
        anchors.centerIn: parent

        TextField { id: nameField; placeholderText: qsTr("Nombre") }
        TextField { id: emailField; placeholderText: qsTr("Email") }
        TextField { id: typeField; placeholderText: qsTr("Tipo") }
        TextField { id: companyIDField; placeholderText: qsTr("Company ID") }
        TextField { id: ageField; placeholderText: qsTr("Edad"); inputMethodHints: Qt.ImhDigitsOnly }
        TextField { id: cityField; placeholderText: qsTr("Ciudad") }
        TextField { id: occupationField; placeholderText: qsTr("Ocupación") }
        TextField { id: portionsField; placeholderText: qsTr("Porciones"); inputMethodHints: Qt.ImhDigitsOnly }
        TextField { id: passwordField; placeholderText: qsTr("Contraseña"); echoMode: TextInput.Password }

        Button {
            text: qsTr("Crear usuario")
            onClicked: {
                function safeInt(val) {
                    var n = parseInt(val); return isNaN(n) ? 0 : n;
                }
                var userData = {
                    name: nameField.text,
                    email: emailField.text,
                    type: typeField.text,
                    companyID: companyIDField.text,
                    age: safeInt(ageField.text),
                    city: cityField.text,
                    occupation: occupationField.text,
                    portions: safeInt(portionsField.text),
                    password: passwordField.text
                }
                myMachine.createUser(userData)
            }
        }
    }
}
