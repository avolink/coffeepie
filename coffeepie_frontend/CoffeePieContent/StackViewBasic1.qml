import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15  // Import for GridLayout
Item {
    id: root
    width: 1920
    height: 824
 property var vmList: []  // Define a property to store the VM list
 property string ipAddress: "" 
   
    StackView {
        id: stackViewBasic
        x: 0
        y: 0
        width: 1920
        height: 788
    }

   ScrollView {
        id: scrollView
        anchors.fill: parent
        contentItem: GridLayout {
            id: vmListContainer
            columns: 3  // Set 3 VMs per row
            columnSpacing: 20
            rowSpacing: 20
            anchors.margins: 20
              width: parent.width  // Ensure the GridLayout takes the full width of the ScrollView
              implicitHeight: childrenRect.height 
        }
    }

        // Add the LoadingIndicator
    Loader {
        id: loadingIndicator
        anchors.centerIn: parent
        visible: false
        source: "LoadingIndicator.qml"  // Path to your LoadingIndicator.qml
    }
 // PIN Dialog
    Dialog {
        id: pinDialog
        title: "Enter PIN for Sunshine Pairing"
        modal: true
        visible: false
      
        Column {
            spacing: 10
            TextField {
                id: pinInput
                placeholderText: "Enter 4-digit PIN"
                inputMethodHints: Qt.ImhDigitsOnly
            }
            TextField {
                id: clientNameInput
                placeholderText: "Enter Client Name"
            }
            Row {
                spacing: 3
                Button {
                    text: "Submit"
                    onClicked: {
                        if (pinInput.text.length === 4 && clientNameInput.text.length > 0) {
                            pinDialog.visible = false;
                            myMachine.sendPinToSunshine(ipAddress, pinInput.text, clientNameInput.text);
                        } else {
                            console.log("Invalid input. Please enter a valid PIN and client name.");
                        }
                    }
                }
                Button {
                    text: "Cancel"
                    onClicked: pinDialog.visible = false
                }
            }
        }
    }

    Connections {
        target: myMachine
        function onVmListUpdated(vms) {
             console.log("VM List Updated:", vms); 
            vmList = vms;  // Assign the emitted list to the vmList property

            // Clear existing widgets
            for (let i = vmListContainer.children.length - 1; i >= 0; i--) {
                vmListContainer.children[i].destroy();
            }

            // Dynamically create widgets for each VM in the list
            for (let i = 0; i < vmList.length; i++) {
                let component = vmWidget.createObject(vmListContainer, { vmId: vmList[i] });
                if (component) {
                    component.parent = vmListContainer;
                }
            }

            // Add a "New Machine" button at the end
            let newMachineComponent = newMachineWidget.createObject(vmListContainer);
            if (newMachineComponent) {
                newMachineComponent.parent = vmListContainer;
            }
        }
         }
     

      Connections {
        target: myMachine
        function onVmStarted(success, vmId) {
            loadingIndicator.visible = false;  // Hide the loading indicator
            if (success) {
                console.log("VM started successfully!");
               //  myMachine.fetchVmIp("N001", vmId);
            } else {
                console.log("Failed to start VM.");
        }
    }
           function onVmIpFetched(ipAddress, vmId) {
        for (let i = 0; i < vmListContainer.children.length; i++) {
            let child = vmListContainer.children[i];
            if (child.vmId === vmId) {  // Match the vmId
                if (ipAddress) {
                    console.log("Fetched IP address:", ipAddress);
                    //child.text3.text = `IP: ${ipAddress}`; 
                     // Update the text3 element

                       root.ipAddress = ipAddress;  // Store the IP address
                   //  let isFirstTimeConnection = true; // Replace with actual logic
                    
                   let isFirstTimeConnection = !myMachine.isHostPaired(ipAddress);
                     // Show the PIN dialog
                     console.log(isFirstTimeConnection);
                     if (isFirstTimeConnection) {
                         pinDialog.visible = true;
                       console.log("Attempting to pair with host:", ipAddress);
                       myMachine.pair_with_moonlight(ipAddress);
                      } else {
                // Proceed with PIN dialog for Sunshine or direct streaming
                      root.ipAddress = ipAddress;
                      //pinDialog.visible = true;
                     pinDialog.visible = false; // Hide the PIN dialog
                    console.log("Skipping pairing. Starting stream directly...");
                    myMachine.stream_with_moonlight(ipAddress, "desktop", "1080", "60");
    
                    }
                } else {
                    console.log("Failed to fetch IP address.");
                    child.text3.text = "IP: Not available";
                }
                break;
            }
        }
    }
         function onPinSent(success, message) {
            if (success) {
                console.log("PIN sent successfully:", message);
            } else {
                console.log("Failed to send PIN:", message);
            }
        }


     function onMoonlightClosed() {
        console.log("Moonlight closed. Hiding PIN dialog.");
        pinDialog.visible = false;  // Hide the PIN dialog
    }



    }

   Component {
    id: vmWidget
    Item {
         property alias text3: text3 
         property string vmId  
        width: 550
        height: 375

        Image {
            id: oS_Selector_Background
            x: 0
            y: 0
            width: parent.width
            height: parent.height
            source: "images/OS_Selector_Background.png"
            fillMode: Image.PreserveAspectFit
        }

        TextInput {
            id: textInput
            x: 133
            y: 22
            width: 284
            height: 52
            color: "#f2f8f9"
            text: qsTr("Mi Máquina")
            font.pixelSize: 30
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            selectionColor: "#565151"
        }

        Text {
            id: text1
            x: 29
            y: 307
            width: 241
            height: 39
            color: "#f2f8f9"
            text:  vmId
            font.pixelSize: 28
            horizontalAlignment: Text.AlignLeft
            verticalAlignment: Text.AlignBottom
        }

        Text {
            id: text2
            x: 276
            y: 307
            width: 235
            height: 39
            color: "#f2f8f9"
            text: qsTr("700 Cr/hora")
            font.pixelSize: 28
            horizontalAlignment: Text.AlignRight
            verticalAlignment: Text.AlignBottom
        }

        Button {
            id: button
            x: 458
            y: 21
            width: 65
            height: 65
            icon.height: 60
            icon.width: 60
            icon.color: "#f2f8f9"
            icon.source: "images/Menu_Button.png"
            flat: true

            Connections {
                target: button
                function onClicked() { stackView.push("Contextual_Menu.qml") }
            }
        }

        Button {
            id: button1
            x: 125
            y: 101
            width: 300
            height: 200
            icon.height: 200
            icon.width: 200
            icon.color: "#00000000"
            icon.source: "images/Operating_Systems/W10_Icon.png"
            flat: true

            Connections {
                target: button1
                function onClicked() { console.log("VM ID clicked:", vmId); myMachine.startVM("N001", vmId);    myMachine.fetchVmIp("N001", vmId);//root.ipAddress = ipAddress;  // Store the IP address
                  //  pinDialog.visible = true; 
                    }
            }
        }
           
        Text {
            id: text3
            x: 154
            y: 66
            width: 243
            height: 39
            color: "#e1cfb2b2"
            text: qsTr("Creado")
            font.pixelSize: 22
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignTop
        }
    }
}

    Component {
        id: newMachineWidget
        Button {
            width: 550
            height: 375
            icon.width: 537
            icon.height: 360
            icon.source: "images/New_Machine_Button.png"
            icon.color: "#007a2828"
            flat: true
            onClicked: stackView.push("Basic_OS_Selection.qml")
        }
    }

    Component.onCompleted: {
        myMachine.fetchVMList("N001"); // Fetch the VM list for node "N001"
    }

    
}




