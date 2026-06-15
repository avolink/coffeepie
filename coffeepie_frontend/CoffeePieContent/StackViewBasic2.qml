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
          hoverEnabled: true
     //   active: hovered || pressed
      //  orientation: Qt.Vertical
      //  size: frame.height / content.height
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.bottom: parent.bottom

         ScrollBar.vertical: ScrollBar {  // Attach the ScrollBar to the ScrollView
            policy: ScrollBar.AsNeeded
        interactive: true
        }

        Column {
            id: contentColumn
        width: scrollView.width
        spacing: 0
        
         GridLayout {
            id: vmListContainer
            columns: 3  // Set 3 VMs per row
            columnSpacing: 10
            rowSpacing: 10
            anchors.left: parent.left
            anchors.right: parent.right
            width: parent.width
            //anchors.top: parent.top
             // anchors.fill: parent  
           // anchors.margins: 20
            //  width: parent.width  // Ensure the GridLayout takes the full width of the ScrollView
         //     implicitHeight: childrenRect.height 
              
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
  
    Connections {
        target: myMachine
        function onVmListUpdated(vms) {
            console.log("VM List Updated:", vms); 
            vmList = vms;  // Assign the emitted list to the vmList property

            // Clear existing widgets
            for (let i = vmListContainer.children.length - 1; i >= 0; i--) {
                vmListContainer.children[i].destroy();
            }
              // Add a "New Machine" button at the end
            let newMachineComponent = newMachineWidget.createObject(vmListContainer);
            if (newMachineComponent) {
                newMachineComponent.parent = vmListContainer;
            }
            // Dynamically create widgets for each VM in the list
            for (let i = 0; i < vmList.length; i++) {
                let component = vmWidget.createObject(vmListContainer, { vmId: vmList[i] });
                if (component) {
                    component.parent = vmListContainer;
                }
            }

           
        }
    }

    function fetchAndRenderVMs() {
        if (!myMachine.userToken) return;
        var vms = myMachine.fetchMyVMs(myMachine.userToken);
        vmList = vms || [];  // Use empty array if vms is null
        
        // Clear existing widgets
        for (let i = vmListContainer.children.length - 1; i >= 0; i--) {
            vmListContainer.children[i].destroy();
        }
        
        // Always add "New Machine" button
        let newMachineComponent = newMachineWidget.createObject(vmListContainer);
        if (newMachineComponent) {
            newMachineComponent.parent = vmListContainer;
        }
        
        // Add VM widgets if any exist
        if (vms && vms.length) {
            for (let i = 0; i < vmList.length; i++) {
                let vm = vmList[i];
                let component = vmWidget.createObject(vmListContainer, {
                    vmId: vm.vmid,
                    name: vm.name,
                    credits: vm.credits_for_minutes,
                    status: vm.status,
                    so: vm.specs ? vm.specs.so : "",
                    cpu: vm.specs ? vm.specs.cpu : 0,
                    memory: vm.specs ? vm.specs.memory : 0,
                    id: vm.id,
                    storage: vm.specs ? vm.specs.storage : 0
            
                });
                if (component) {
                    component.parent = vmListContainer;
                }
            }
        }
    }

    Component.onCompleted: {
        if (myMachine.userToken) fetchAndRenderVMs();
        else {
            // Show "New Machine" button even without token being ready
            let newMachineComponent = newMachineWidget.createObject(vmListContainer);
            if (newMachineComponent) {
                newMachineComponent.parent = vmListContainer;
            }
        }
    }

    Component {
        id: vmWidget
        Item {
            property string vmId
            property string name
            property real credits
            property string status
            property string so
            property int cpu
            property int memory
            property int storage
            property string id
            property string node
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
                text: name
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
                text: credits + " Cr/minuto"
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
                    function onClicked() {
                        myMachine.selectedVmId = id;
                         myMachine.vmCredits = credits; // Set global selected VM ID
                        stackView.push("Contextual_Menu.qml");
                    }
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
                icon.source: so === "win10" ? "images/Operating_Systems/W10_Icon.png" : so === "linux" ? "images/Operating_Systems/Linux_Icon.png" : "images/Operating_Systems/Default_Icon.png"
                flat: true

                Connections {
                    target: button1
                    function onClicked() {
                        if (!myMachine.userToken) return;
                        console.log("VM VmID clicked:", vmId);
                        console.log("VM ID clicked:", id);
                        var result = myMachine.getConsoleUrl(myMachine.userToken, id);
                        if (result && result.success === false) {
                            errorDialog.errorText = result.detail;
                            errorDialog.visible = true;
                        }
                    }
                }
            }
               
            Text {
                id: text3
                x: 160
                y: 66
                width: 243
                height: 39
                color: "#e1cfb2b2"
                text: status
                font.pixelSize: 22
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignTop
            }
            // Add specs display
            Text {
                x: 23; y: 280; color: "#f2f8f9"; font.pixelSize: 18;
                text: "CPU: " + cpu + ", RAM: " + memory + "MB, Disk: " + storage + "MB, SO: " + so
            }
        }
    }

   // Component.onCompleted: {
   //     myMachine.fetchVMList("N001"); // Fetch the VM list for node "N001"
   // }

    Dialog {
        id: errorDialog
        property string errorText: ""
        title: qsTr("Error")
        visible: false
        standardButtons: Dialog.Ok
        onAccepted: visible = false
        Text {
            text: errorDialog.errorText
            color: "red"
            wrapMode: Text.WordWrap
        }
    }
    
}




