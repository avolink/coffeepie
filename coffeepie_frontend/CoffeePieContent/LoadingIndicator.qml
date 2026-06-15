import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    width: 100
    height: 100

    Rectangle {
        anchors.fill: parent
        color: "black"
        opacity: 0.5
        radius: 10
    }

    BusyIndicator {
        anchors.centerIn: parent
        running: true
        width: 50
        height: 50
    }
}