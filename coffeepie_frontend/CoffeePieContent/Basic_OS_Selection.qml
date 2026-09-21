import QtQuick   2.15
import QtQuick.Controls   2.15

Item {
    id: root
    width: 1920
    height: 1080
 z: 2

    StackView {
        id: stackViewBasicOSselection
        x: 0
        y: 0
        width: 1920
        height: 1080








         Image {
            id: coffee_Background
            x: 0
            y: 0
            width: 1920
            height: 1080
            source: "images/Coffee_Background.jpg"
            sourceSize.height: 1080
            sourceSize.width: 1920
            fillMode: Image.Stretch
         }

        Button {
            id: buttonBack
            x: 1776
            y: 20
            width: 120
            height: 120
            icon.width: 100
            icon.source: "images/Back_Button.png"
            icon.height: 100
            icon.color: "#eaeaea"
            flat: true
            Connections {
                target: buttonBack
                onClicked: stackView.clear(StackView.Immediate)
            }
        }

        ScrollView {
            id: scrollView
            x: 0
            y: 251
            width: 1917
            height: 826
            rotation: -0.066


            Image {
                id: oS_Selector_Background
                x: 92
                y: 30
                source: "../CoffeePieContent/images/OS_Selector_Background.png"
                fillMode: Image.PreserveAspectFit

                Button {
                    id: button1
                    x: 151
                    y: 103
                    width: 235
                    height: 154
                    icon.width: 90
                    icon.source: "images/Operating_Systems/W11_Icon.png"
                    icon.height: 90
                    icon.color: "#007a2828"
                    onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                }

                Text {
                    id: _text
                    x: 67
                    y: 31
                    width: 401
                    height: 55
                    color: "#eaeaea"
                    text: qsTr("Windows 11")
                    font.pixelSize: 36
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                Text {
                    id: _text6
                    x: 28
                    y: 289
                    width: 485
                    height: 55
                    color: "#eaeaea"
                    text: qsTr("Desde 180 Cr/min")
                    font.pixelSize: 36
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                }

                MouseArea {
                    id: mouseArea1
                    x: 0
                    y: 0
                    width: 537
                    height: 360

                    Connections {
                        target: mouseArea1
                        onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                    }
                }
            }

            Image {
                id: oS_Selector_Background1
                x: 702
                y: 30
                source: "../CoffeePieContent/images/OS_Selector_Background.png"
                fillMode: Image.PreserveAspectFit
                Button {
                    id: button2
                    x: 151
                    y: 103
                    width: 235
                    height: 154
                    icon.width: 100
                    icon.source: "images/Operating_Systems/W10_Icon.png"
                    icon.height: 100
                    icon.color: "#007a2828"
                    onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                }
            }

            Image {
                id: oS_Selector_Background2
                x: 702
                y: 436
                source: "../CoffeePieContent/images/OS_Selector_Background.png"
                fillMode: Image.PreserveAspectFit

                Button {
                    id: button5
                    x: 151
                    y: 103
                    width: 235
                    height: 154
                    icon.color: "#007a2828"
                    icon.height: 100
                    icon.width: 100
                    icon.source: "images/Operating_Systems/Bodhi_Linux_Icon.png"
                    onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                }
            }

            Image {
                id: oS_Selector_Background3
                x: 1305
                y: 29
                source: "../CoffeePieContent/images/OS_Selector_Background.png"
                fillMode: Image.PreserveAspectFit

                Button {
                    id: button3
                    x: 151
                    y: 103
                    width: 235
                    height: 154
                    icon.color: "#007a2828"
                    icon.height: 100
                    icon.width: 100
                    icon.source: "images/Operating_Systems/Steam_OS_Icon.png"
                    onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                }
            }

            Image {
                id: oS_Selector_Background4
                x: 92
                y: 436
                source: "../CoffeePieContent/images/OS_Selector_Background.png"
                fillMode: Image.PreserveAspectFit

                Button {
                    id: button4
                    x: 151
                    y: 103
                    width: 235
                    height: 154
                    icon.color: "#007a2828"
                    icon.height: 100
                    icon.width: 100
                    icon.source: "images/Operating_Systems/Linux_Mint_Icon.png"
                    onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                }

                MouseArea {
                    id: mouseArea4
                    x: 0
                    y: 0
                    width: 537
                    height: 360

                    Connections {
                        target: mouseArea4
                        onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                    }
                }
            }

            Image {
                id: oS_Selector_Background5
                x: 1305
                y: 435
                source: "../CoffeePieContent/images/OS_Selector_Background.png"
                fillMode: Image.PreserveAspectFit

                Button {
                    id: button6
                    x: 151
                    y: 103
                    width: 235
                    height: 154
                    icon.color: "#007a2828"
                    icon.height: 130
                    icon.width: 130
                    icon.source: "images/Operating_Systems/Docker_OS_Icon.png"
                    onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                }
            }

            Text {
                id: _text1
                x: 771
                y: 56
                width: 401
                height: 55
                color: "#eaeaea"
                text: qsTr("Windows 10")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: _text2
                x: 1373
                y: 56
                width: 401
                height: 55
                color: "#eaeaea"
                text: qsTr("Steam OS")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: _text3
                x: 142
                y: 459
                width: 401
                height: 55
                color: "#eaeaea"
                text: qsTr("Linux Mint")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: _text4
                x: 770
                y: 459
                width: 401
                height: 55
                color: "#eaeaea"
                text: qsTr("Bodhi Linux")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: _text5
                x: 1373
                y: 459
                width: 401
                height: 55
                color: "#eaeaea"
                text: qsTr("Ubuntu Server Docker ")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: _text7
                x: 729
                y: 319
                width: 485
                height: 55
                color: "#eaeaea"
                text: qsTr("Desde 120 Cr/min")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: _text8
                x: 1331
                y: 320
                width: 485
                height: 55
                color: "#eaeaea"
                text: qsTr("Desde 120 Cr/min")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: _text9
                x: 118
                y: 726
                width: 485
                height: 55
                color: "#eaeaea"
                text: qsTr("Desde 60 Cr/min")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: _text10
                x: 728
                y: 725
                width: 485
                height: 55
                color: "#eaeaea"
                text: qsTr("Desde 30 Cr/min")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                id: _text11
                x: 1331
                y: 725
                width: 485
                height: 55
                color: "#eaeaea"
                text: qsTr("Desde 30 Cr/min")
                font.pixelSize: 36
                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignVCenter
            }

            MouseArea {
                id: mouseArea2
                x: 702
                y: 29
                width: 537
                height: 360

                Connections {
                    target: mouseArea2
                    onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                }
            }

            MouseArea {
                id: mouseArea3
                x: 1305
                y: 33
                width: 537
                height: 357

                Connections {
                    target: mouseArea3
                    onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                }
            }

            MouseArea {
                id: mouseArea5
                x: 702
                y: 436
                width: 537
                height: 359

                Connections {
                    target: mouseArea5
                    onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                }
            }

            MouseArea {
                id: mouseArea6
                x: 1305
                y: 436
                width: 537
                height: 359

                Connections {
                    target: mouseArea6
                    onClicked: stackView.push("Modify_Machine.qml", StackView.Immediate)
                }
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
                function onClicked() { stackViewBasicOSselection.push("About.qml") }
            }
        }

        Text {
            id: labelSelectOS
            x: 368
            y: 99
            width: 1232
            height: 73
            color: "#eaeaea"
            text: qsTr("Selecciona un Sistema Operativo")
            font.pixelSize: 60
            horizontalAlignment: Text.AlignHCenter
        }
    }


}
