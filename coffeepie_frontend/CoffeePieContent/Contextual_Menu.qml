import QtQuick  2.15
import QtQuick.Controls  2.15


Item {
    id: root
    width: 1920
    height: 1080

    MouseArea {
        id: mouseAreaExit
        x: 0
        y: 0
        width: 1920
        height: 1080

        Connections {
            target: mouseAreaExit
            onClicked: stackView.clear()
        }

        Rectangle {
            id: mainMenu
            x: 776
            y: 51
            width: 368
            height: 990
            visible: true
            color: "#908f8f"

            MouseArea {
                id: neutralAreaMenu
                x: 0
                y: 1
                width: 368
                height: 989

                Label {
                    id: labelKeepOn
                    x: 0
                    y: 15
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Mantener Encendida")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelModifyMachine
                    x: -7
                    y: 214
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Modificar Máquina")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelDuplicateMachine
                    x: -7
                    y: 362
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Duplicar Máquina")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelSnapshots
                    x: -7
                    y: 515
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Snapshots (Respaldos)")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelRebootShutdown
                    x: -7
                    y: 666
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Reiniciar o Apagar")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelDeleteMachine
                    x: -7
                    y: 824
                    width: 368
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Eliminar Máquina")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelOn
                    x: 217
                    y: 63
                    width: 66
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("On")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Label {
                    id: labelOff
                    x: 73
                    y: 63
                    width: 72
                    height: 36
                    color: "#f2f8f9"
                    text: qsTr("Off")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pointSize: 20
                }

                Button {
                    id: btn_Edit_Machine
                    x: 115
                    y: 246
                    width: 120
                    height: 120
                    visible: true
                    icon.height: 120
                    icon.width: 120
                    icon.color: "#00000000"
                    icon.source: "images/Contextual_Menu/Btn_Edit_Machine.png"
                    flat: true

                    Connections {
                        target: btn_Edit_Machine
                        onClicked: stackView.push("Modify_Machine1.qml", StackView.Immediate)
                    }
                }

                Button {
                    id: btn_Duplicate_Machine
                    x: 115
                    y: 391
                    width: 120
                    height: 120
                    icon.width: 120
                    icon.source: "images/Contextual_Menu/Btn_Duplicate_Machine.png"
                    icon.height: 120
                    icon.color: "#00000000"
                    flat: true
                    onClicked: {
                        if (!myMachine.userToken || !myMachine.selectedVmId) return;
                        var result = myMachine.cloneVM(myMachine.userToken, myMachine.selectedVmId);
                        if (result && result.success === false) {
                            cloneVmDialog.errorText = result.detail;
                            cloneVmDialog.visible = true;
                        } else {
                            cloneVmDialog.errorText = "VM cloned successfully.";
                            cloneVmDialog.visible = true;
                        }
                    }
                }

                Button {
                    id: btn_Snapshots
                    x: 108
                    y: 544
                    width: 136
                    height: 124
                    icon.width: 120
                    icon.source: "images/Contextual_Menu/Btn_Snapshots.png"
                    icon.height: 120
                    icon.color: "#00000000"
                    flat: true


                    Connections {
                        target: btn_Snapshots
                        onClicked: {
                            if (!myMachine.userToken || !myMachine.selectedVmId) return;
                            var description = "Snapshot created from context menu";
                            var result = myMachine.createSnapshot(myMachine.userToken, myMachine.selectedVmId, description);
                            if (result && result.success === false) {
                                 cloneVmDialog.errorText = result.detail;
                                 cloneVmDialog.visible = true;
                            } else {
                                cloneVmDialog.errorText = "Snapshot created successfully.";
                                 cloneVmDialog.visible = true;
                            }
                        }
                    }
                }

                Button {
                    id: btn_Duplicate_Machine1
                    x: 116
                    y: 698
                    width: 120
                    height: 120
                    icon.width: 120
                    icon.source: "images/Contextual_Menu/Btn_Reboot_Shutdown.png"
                    icon.height: 120
                    icon.color: "#00000000"
                    flat: true
                    onClicked: {
                        if (!myMachine.userToken || !myMachine.selectedVmId) return;
                        var result = myMachine.rebootVM(myMachine.userToken, myMachine.selectedVmId);
                        if (result && result.success === false) {
                            rebootVmDialog.errorText = result.detail;
                            rebootVmDialog.visible = true;
                        } else {
                            rebootVmDialog.errorText = "VM rebooted successfully.";
                            rebootVmDialog.visible = true;
                        }
                    }
                }

Switch {
    id: switchKeepMachineOn
    x: 145
    y: 57
    width: 76
    height: 51
    text: qsTr("")
    
    
     Component.onCompleted: {
        if (myMachine.userToken && myMachine.selectedVmId) {
            var statusResult = myMachine.getVMStatus(myMachine.userToken, myMachine.selectedVmId);
            if (statusResult && statusResult.status === "running") {
                switchKeepMachineOn.checked = true;
            } else {
                switchKeepMachineOn.checked = false;
            }
        }
    }
    onCheckedChanged: {
        if (!myMachine.userToken || !myMachine.selectedVmId) return;
        if (switchKeepMachineOn.checked) {
            // Switch turned ON: Start VM if not running
            var statusResult = myMachine.getVMStatus(myMachine.userToken, myMachine.selectedVmId);
            if (statusResult && statusResult.status !== "running") {
                var result = myMachine.startVM(myMachine.userToken, myMachine.selectedVmId);
                if (result && result.success === false) {
                    startVmDialog.errorText = result.detail;
                    startVmDialog.visible = true;
                } else {
                    startVmDialog.errorText = "VM started successfully.";
                    startVmDialog.visible = true;
                }
            }
        } else {
            // Switch turned OFF: Shutdown VM if running
            var statusResult = myMachine.getVMStatus(myMachine.userToken, myMachine.selectedVmId);
            if (statusResult && statusResult.status === "running") {
                var result = myMachine.shutdownVM(myMachine.userToken, myMachine.selectedVmId);
                if (result && result.success === false) {
                    stopVmDialog.errorText = result.detail;
                    stopVmDialog.visible = true;
                } else {
                    stopVmDialog.errorText = "VM shutdown successfully.";
                    stopVmDialog.visible = true;
                }
            }
        }
    }
    
    
   
}

                Image {
                    id: blank_Square1
                    x: 184
                    y: 111
                    source: "images/Blank_Square.png"
                    fillMode: Image.PreserveAspectFit

                    Button {
                        id: btn_Stop
                        x: 8
                        y: 8
                        width: 88
                        height: 88
                        visible: true
                        text: qsTr("")
                        flat: true
                        clip: false
                        icon.height: 120
                        icon.width: 120
                        icon.color: "#00000000"
                        icon.source: "images/Contextual_Menu/Btn_Stop.png"
                        onClicked: {
                            if (!myMachine.userToken || !myMachine.selectedVmId) return;
                            var result = myMachine.stopVM(myMachine.userToken, myMachine.selectedVmId);
                            if (result && result.success === false) {
                                stopVmDialog.errorText = result.detail;
                                stopVmDialog.visible = true;
                            } else {
                                stopVmDialog.errorText = "VM stopped successfully.";
                                stopVmDialog.visible = true;
                            }
                        }
                    }
                }

                Image {
                    id: blank_Square
                    x: 63
                    y: 111
                    source: "images/Blank_Square.png"
                    fillMode: Image.PreserveAspectFit

                    Button {
                        id: btn_Play_Pause
                        x: 8
                        y: 8
                        width: 88
                        height: 88
                        text: qsTr("")
                        flat: true
                        icon.height: 120
                        icon.width: 120
                        icon.color: "#00000000"
                        icon.source: "images/Contextual_Menu/Btn_Play_Pause.png"
                        onClicked: {
                            if (!myMachine.userToken || !myMachine.selectedVmId) return;
                            var result = myMachine.startVM(myMachine.userToken, myMachine.selectedVmId);
                            if (result && result.success === false) {
                                startVmDialog.errorText = result.detail;
                                startVmDialog.visible = true;
                            } else {
                                startVmDialog.errorText = "VM started successfully.";
                                startVmDialog.visible = true;
                            }
                        }
                    }
                }

                Button {
                    id: btnDeleteMachine
                    x: 117
                    y: 858
                    width: 120
                    height: 123
                    text: qsTr("")
                    icon.height: 120
                    icon.width: 120
                    icon.color: "#00000000"
                    flat: true
                    icon.source: "images/Contextual_Menu/Btn_Delete.png"
                    onClicked: deleteConfirmDialog.visible = true
                }



            }
        }
    }

    Dialog {
        id: startVmDialog
        property string errorText: ""
        title: qsTr("")
        visible: false
        standardButtons: Dialog.Ok
        onAccepted: visible = false
        Text {
            text: startVmDialog.errorText
            color: "red"
            wrapMode: Text.WordWrap
        }
    }

    Dialog {
        id: stopVmDialog
        property string errorText: ""
        title: qsTr("")
        visible: false
        standardButtons: Dialog.Ok
        onAccepted: visible = false
        Text {
            text: stopVmDialog.errorText
            color: "red"
            wrapMode: Text.WordWrap
        }
    }

    Dialog {
        id: rebootVmDialog
        property string errorText: ""
        title: qsTr("")
        visible: false
        standardButtons: Dialog.Ok
        onAccepted: visible = false
        Text {
            text: rebootVmDialog.errorText
            color: "red"
            wrapMode: Text.WordWrap
        }
    }

    Dialog {
        id: cloneVmDialog
        property string errorText: ""
        title: qsTr("")
        visible: false
        standardButtons: Dialog.Ok
        onAccepted: visible = false
        Text {
            text: cloneVmDialog.errorText
            color: "red"
            wrapMode: Text.WordWrap
        }
    }

    Dialog {
        id: deleteConfirmDialog
        title: qsTr("Delete VM")
        visible: false
        standardButtons: Dialog.Ok | Dialog.Cancel
        property string errorText: ""
        onAccepted: {
            if (!myMachine.userToken || !myMachine.selectedVmId) return;
            var result = myMachine.deleteVM(myMachine.userToken, myMachine.selectedVmId);
            if (result && result.success === false) {
                errorText = result.detail;
            } else {
                errorText = "VM deleted successfully.";
            }
            deleteResultDialog.visible = true;
        }
        onRejected: visible = false
        Text {
            text: qsTr("Are you sure you want to delete this VM?")
            color: "red"
            wrapMode: Text.WordWrap
        }
    }
    Dialog {
        id: deleteResultDialog
        title: qsTr("Delete VM Result")
        visible: false
        standardButtons: Dialog.Ok
        onAccepted: visible = false
        Text {
            text: deleteConfirmDialog.errorText
            color: "red"
            wrapMode: Text.WordWrap
        }
    }
}
