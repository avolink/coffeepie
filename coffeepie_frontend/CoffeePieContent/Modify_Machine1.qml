import QtQuick  2.15
import QtQuick.Controls  2.15



Item {
    id: root
    width: 1920
    height: 1080

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
                x: 348
                y: 32
                width: 1404
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
                x: 130
                y: 340
                width: 1646
                height: 108
         
                stepSize: 1
                from: 1
            value: myMachine.vmCredits 


                Text {
                    id: machineDescription
                    x: 4
                    y: 116
                    width: 1638
                    height: 398
                    color: "#eaeaea"
                    
                    font.pixelSize: 32
                    horizontalAlignment: Text.AlignHCenter
                    text: slider.value + " Porciones (" + slider.value * 125 + " GB) te costarán: " + slider.value * 30 + " Cr/min\n" + slider.value * 1 + " Wh Consumo Eléctrico\n"+ slider.value * 1 + " Núcleos Lógicos\n" + slider.value * 1 + " GB RAM\n"+ slider.value * 8 + " GB SSD\n" + slider.value * 125 + " GB HDD\n"   + slider.value * 125 + " MB VRAM\n"+ slider.value * 8 + " Mbps Ancho de Banda\n"+ slider.value * 3 + " MPX/s Resolución/Tasa Refresco\n";

                }

                Connections {
                    target: slider
                    function onValueChanged() { machineDescription.text = slider.value + " Porciones (" + slider.value * 125 + " GB) te costarán: " + slider.value * 30 + " Cr/min\n"
                                               + slider.value * 1 + " Wh Consumo Eléctrico\n"
                                               + slider.value * 1 + " Núcleos Lógicos\n"
                                               + slider.value * 1 + " GB RAM\n"
                                             + slider.value * 8 + " GB SSD\n"
                                              + slider.value * 125 + " GB HDD\n"
                                               + slider.value * 125 + " MB VRAM\n"
                                             + slider.value * 8 + " Mbps Ancho de Banda\n"
                                              + slider.value * 3 + " MPX/s Resolución/Tasa Refresco\n"
                   }


                  
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
                y: 160
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

                Rectangle {
                    id: rectangleDark1
                    x: 7
                    y: 12
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

                    Image {
                        id: frame1
                        x: -9
                        y: -11
                        source: "images/Recurrence_Button.png"
                        fillMode: Image.PreserveAspectFit

                        Text {
                            id: hourlyRate
                            x: 44
                            y: 92
                            width: 478
                            height: 56
                            color: "#ffffff"
                            text: qsTr("30 Cr")
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
                            text: qsTr("Porción/Minuto")
                            horizontalAlignment: Text.AlignHCenter
                            styleColor: "#ffffff"
                            font.pointSize: 30
                            font.bold: false
                        }
                    }
                }
            }
            MouseArea {
                id: selectorMonthly
                x: 680
                y: 160
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

                Rectangle {
                    id: rectangleDark2
                    x: 8
                    y: 12
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

                    Image {
                        id: frame2
                        x: -10
                        y: -11
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
                }
            }

            MouseArea {
                id: selectorYearly
                x: 1300
                y: 160
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

                Rectangle {
                    id: rectangleDark3
                    x: 12
                    y: 13
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

                    Image {
                        id: frame3
                        x: -14
                        y: -12
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

            RoundButton {
                id: buttonSubstractSlice
                x: 24
                y: 364
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
                y: 364
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
                    y: 22
                    width: 96
                    height: 55
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

        Button {
            id: buttonOS
            x: 180
            y: 31
            width: 139
            height: 94
            icon.width: 100
            icon.source: "../CoffeePieContent/images/Operating_Systems/W10_Icon.png"
            icon.height: 100
            icon.color: "#007a2828"
        }


        Image {
    id: input_Field_Vector1
    x:690
    y: 820
    width: 479
    height: 68
    source: "images/Input_Field_Vector.png"
    fillMode: Image.Stretch
}

TextField {
    id: inputFieldnamechine
    x: 690
    y: 830
    width: 458
    height: 51
    visible: true
    selectionColor: "#908f8f"
    selectedTextColor: "#ffffff"
    placeholderText: qsTr("nombre de vm")
    inputMask: ""
    font.pointSize: 20
    onFocusChanged: if (focus) selectAll()
    background: Rectangle {
        color: flat
    }
}


        Image {
            id: modifyButton
            x: 697
            y: 913
            source: "images/Create_Button.png"
            fillMode: Image.PreserveAspectFit

            Button {
                id: buttonCreate
                x: 0
                y: 2
                width: 427
                height: 130
                icon.color: "#ffffff"
                font.pointSize: 30
                flat: true

                Connections {
                    target: buttonCreate
                    onClicked: StackView.clear()
                }

                Text {
                    id: lblModifyMachine
                    x: 15
                    y: 6
                    width: 498
                    height: 116
                    color: "#ffffff"
                    text: qsTr("Continuar")
                    font.pixelSize: 44
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.bold: false
                }

                Connections {
                    target: buttonCreate
                    function onClicked() { 
                         var specs = {
                namevm: inputFieldnamechine.text,
                source_name: "111",
                node: "N001",
                storage: "local-lvm",
                full: 0,
                ipconfig0: "string",
                cores: slider.value * 1,
                sockets: 1,
                memory: slider.value * 1000,
                disk: "ide0",
                disk_size: (slider.value * 125) + "G",
                credits_for_minutes: slider.value * 30
            };
            var result = myMachine.cloneVMWithSpecs(myMachine.userToken, specs);
            var result = myMachine.cloneVMWithSpecs(myMachine.userToken, specs);
    if (result && result.success === false) {
        resultDialog.message = result.detail;
        resultDialog.visible = true;
    } else {
        resultDialog.message = "Máquina clonada exitosamente.";
        resultDialog.visible = true;
    }
                        
                        
                        
                        
                        
                        
                        stackView.clear() }
                }
            }
        }
    }


Dialog {
    id: resultDialog
    property string message: ""
    title: "Resultado"
    visible: false
    standardButtons: Dialog.Ok
    onAccepted: visible = false

    Text {
        text: resultDialog.message
        color: "white"
        wrapMode: Text.WordWrap
    }
}


}


