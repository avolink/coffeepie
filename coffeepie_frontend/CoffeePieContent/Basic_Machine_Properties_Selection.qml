import QtQuick   2.15
import QtQuick.Controls   2.15


Item {
    id: root
    width: 1920
    height: 1080
       z: 3
    StackView {
        id: stackViewBasicMachinePropertiesSelection
        x: 0
        y: 0
        width: 1920
        height: 1080

        Image {
            id: coffee_Background
            width: 1920
            height: 1080
            opacity: 1
            source: "images/Coffee_Background.jpg"
            sourceSize.height: 1080
            sourceSize.width: 1920
            fillMode: Image.Stretch

            Text {
                id: labelLogin
                x: 97
                y: 223
                width: 1726
                height: 73
                color: "#ffffff"
                text: qsTr("Elije la Recurrencia y Capacidad de la Máquina")
                font.pixelSize: 60
                horizontalAlignment: Text.AlignHCenter
            }

            Button {
                id: buttonHelp
                x: 33
                y: 33
                width: 120
                height: 80
                icon.width: 100
                icon.source: "../CoffeePieContent/images/Support_Button.png"
                icon.height: 100
                icon.color: "#eaeaea"
                flat: true

                Connections {
                    target: buttonHelp
                    function onClicked() { stackViewBasicMachinePropertiesSelection.push("About.qml") }
                }
            }

            Slider {
                id: slider
                x: 135
                y: 661
                width: 1646
                height: 108
                value: 4
                stepSize: 1
                from: 1
                Text {
                    id: machineDescription
                    x: 2
                    y: 99
                    width: 1638
                    height: 87
                    color: "#eaeaea"
                    text: qsTr("4 Porciones (500GB) te costarán: 2800 Cr/hora")
                    font.pixelSize: 50
                    horizontalAlignment: Text.AlignHCenter
                }

                Connections {
                    target: slider
                    function onValueChanged() { machineDescription.text = slider.value + " Porciones (" + slider.value * 125 + " GB) te costarán: " + slider.value * 700 + " Cr/hora" }
                }
                to: 256
            }

            Button {
                id: buttonBack
                x: 1780
                y: 13
                width: 120
                height: 120
                text: qsTr("")
                icon.height: 100
                icon.width: 100
                icon.color: "#007a2828"
                icon.source: "../CoffeePieContent/images/Back_Button.png"
                flat: true
                Connections {
                    target: buttonBack
                    onClicked: stackView.pop("Basic_OS_Selection.qml", StackView.Immediate)
                }
            }




            MouseArea {
                id: selectorHourly
                x: 58
                y: 397
                width: 561
                height: 179

                Connections {
                    target: selectorHourly
                    function onClicked() {
                        rectangleLight1.visible = true;
                        rectangleLight2.visible = false;
                        rectangleLight3.visible = false;
                        recurrence = "hourly"
                        recurrenceRate = 700;
                    }
                }
            }
            MouseArea {
                id: selectorMonthly
                x: 680
                y: 397
                width: 564
                height: 179

                Connections {
                    target: selectorMonthly
                    function onClicked() {
                        rectangleLight1.visible = false;
                        rectangleLight2.visible = true;
                        rectangleLight3.visible = false;
                        recurrence = "monthly"
                        recurrenceRate = 500000;
                    }
                }
            }

            MouseArea {
                id: selectorYearly
                x: 1300
                y: 397
                width: 563
                height: 179

                Connections {
                    target: selectorYearly
                    function onClicked() {
                        rectangleLight1.visible = false;
                        rectangleLight2.visible = false;
                        rectangleLight3.visible = true;
                        recurrence = "yearly"
                        recurrenceRate = 6000000;
                    }
                }
            }

            RoundButton {
                id: buttonSubstractSlice
                x: 24
                y: 666
                width: 100
                height: 100
                icon.height: 170
                icon.width: 170
                icon.color: "#00000000"

                Image {
                    id: coffee_Pie_Logo
                    x: 5
                    y: 14
                    width: 94
                    height: 59
                    source: "images/Coffee_Pie_Logo.png"
                    fillMode: Image.PreserveAspectFit
                }

                Connections {
                    target: buttonSubstractSlice
                    function onClicked() { slider.value = slider.value - 1 }
                }
            }

            RoundButton {
                id: buttonAddSlice
                x: 1790
                y: 667
                width: 103
                height: 103
                spacing: 0
                icon.cache: true
                font.pointSize: 1
                icon.height: 100
                icon.width: 100
                icon.color: "#00000000"

                Image {
                    id: coffee_Pie_Full
                    x: 0
                    y: 24
                    source: "images/Coffee_Pie_Full.png"
                    fillMode: Image.PreserveAspectFit
                }

                Connections {
                    target: buttonAddSlice
                    function onClicked() { slider.value = slider.value + 1 }
                }
            }

            Connections {
                target: coffee_Background
                function onActiveFocusChanged() { console.log("clicked") }
            }
        }

        Rectangle {
            id: rectangleDark1
            x: 65
            y: 409
            width: 547
            height: 155
            color: "#323030"

            Rectangle {
                id: rectangleLight1
                x: 0
                y: 0
                width: 547
                height: 155
                color: "#565151"
            }
        }


        Rectangle {
            id: rectangleDark2
            x: 688
            y: 409
            width: 546
            height: 155
            color: "#323030"

            Rectangle {
                id: rectangleLight2
                x: 0
                y: 0
                width: 546
                height: 155
                visible: false
                color: "#565151"
            }
        }

        Rectangle {
            id: rectangleDark3
            x: 1312
            y: 410
            width: 544
            height: 160
            color: "#323030"

            Rectangle {
                id: rectangleLight3
                x: -3
                y: 0
                width: 543
                height: 160
                visible: false
                color: "#565151"
            }
        }
        Button {
            id: buttonOS
            x: 843
            y: 38
            width: 235
            height: 154
            icon.width: 100
           
           icon.source: "../CoffeePieContent/images/Operating_Systems/W10_Icon.png"
            icon.height: 100
            icon.color: "#007a2828"
         
        }

        Image {
            id: frame1
            x: 56
            y: 398
            source: "images/Recurrence_Button.png"
            fillMode: Image.PreserveAspectFit

            Text {
                id: hourlyRate
                x: 44
                y: 92
                width: 478
                height: 56
                color: "#ffffff"
                text: qsTr("700 Cr")
                font.pixelSize: 38
                horizontalAlignment: Text.AlignHCenter
            }

            Label {
                id: labelHourlyRate
                x: 39
                y: 29
                width: 478
                height: 53
                color: "#ffffff"
                text: qsTr("Porción/Hora")
                horizontalAlignment: Text.AlignHCenter
                styleColor: "#ffffff"
                font.pointSize: 30
                font.bold: false
            }
        }

        Image {
            id: frame2
            x: 678
            y: 398
            source: "images/Recurrence_Button.png"
            fillMode: Image.PreserveAspectFit

            Text {
                id: monthlyRate
                x: 44
                y: 93
                width: 478
                height: 56
                color: "#ffffff"
                text: qsTr("500'000 Cr")
                font.pixelSize: 38
                horizontalAlignment: Text.AlignHCenter
            }

            Label {
                id: labelMonthlyRate
                x: 44
                y: 27
                width: 478
                height: 53
                color: "#ffffff"
                text: qsTr("Porción/Mes")
                horizontalAlignment: Text.AlignHCenter
                styleColor: "#ffffff"
                font.pointSize: 30
                font.bold: false
            }
        }

        Image {
            id: create_Button
            x: 697
            y: 887
            source: "images/Create_Button.png"
            fillMode: Image.PreserveAspectFit
        }

        Button {
            id: buttonCreate
            x: 697
            y: 887
            width: 527
            height: 130
            icon.color: "#ffffff"
            font.pointSize: 30
            flat: true

            Connections {
                target: buttonCreate
                onClicked:  {
                 
                 StackView.clear(); 
                 }
            }

            Text {
                id: _text1
                x: 14
                y: 6
                width: 498
                height: 116
                color: "#ffffff"
                text: qsTr("Crear Máquina")
                font.pixelSize: 44
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.bold: false
            }

            Connections {
                target: buttonCreate
                function onClicked() {
                     myMachine.createAndStreamVM("111", "N001", "windows10");
                 console.log("Crear Máquina button clicked"); 
                    stackView.clear() 
                     myMachine.fetchVMList("N001");
                    stackView.push("Home_Screen.qml", StackView.Immediate);
                    }
            }
        }

        Image {
            id: frame3
            x: 1298
            y: 398
            source: "images/Recurrence_Button.png"
            fillMode: Image.PreserveAspectFit

            Text {
                id: yearlyRate
                x: 44
                y: 88
                width: 478
                height: 56
                color: "#ffffff"
                text: qsTr("6'000'000 Cr")
                font.pixelSize: 38
                horizontalAlignment: Text.AlignHCenter
            }

            Label {
                id: labelYearlyRate
                x: 44
                y: 29
                width: 478
                height: 53
                color: "#ffffff"
                text: qsTr("Porción/Año")
                horizontalAlignment: Text.AlignHCenter
                styleColor: "#ffffff"
                font.pointSize: 30
                font.bold: false
            }
        }
    }
}


