import QtQuick 2.15
import QtQuick.Controls 2.15

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

    Rectangle {
        id: mainMenu
        x: 0
        y: 0
        width: 1920
        height: 1080
        visible: true
        color: "#ffffff"
        Button {
            id: buttonClose
            x: 1812
            y: 10
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

}
