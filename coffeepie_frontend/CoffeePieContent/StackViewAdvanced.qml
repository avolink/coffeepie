import QtQuick 2.15
import QtQuick.Controls 2.15
import Qt.labs.qmlmodels 1.0


Item {
    id: root
    width: 1920
    height: 826

    StackView {
        id: stackViewAdvanced
        x: 0
        y: 0
        width: 1920
        height: 826

    TableView {
        anchors.fill: parent
        columnSpacing: 0
        rowSpacing: 0
        boundsBehavior: Flickable.StopAtBounds

        model: TableModel {
            TableModelColumn { display: "checked" }
            TableModelColumn { display: "machineCustomName" }
            TableModelColumn { display: "amount" }
            TableModelColumn { display: "machineOS" }
            TableModelColumn { display: "currentSlices" }
            TableModelColumn { display: "fruitColor" }
            TableModelColumn { display: "fruitShape" }
            TableModelColumn { display: "fruitFlavor" }

              // Each row is one type of fruit that can be ordered
              rows: [
                  {
                      // Each property is one cell/column.
                      checked: false,
                      amount: 1,
                      machineCustomName: "Mi Máquina Personal",
                      machineOS: "Windows 10",
                      currentSlices: 8,
                      fruitColor: "Red",
                      fruitShape: "Round",
                      fruitFlavor: "Sweet"
                  },
                  {
                      checked: false,
                      amount: 1,
                      machineCustomName: "Mi Workstation",
                      machineOS: "Windows 11",
                      currentSlices: 16,
                      fruitColor: "Red",
                      fruitShape: "Round",
                      fruitFlavor: "Sweet"
                  },
                  {
                      checked: false,
                      amount: 1,
                      machineCustomName: "Production DB",
                      machineOS: "Debian",
                      currentSlices: 2,
                      fruitColor: "Red",
                      fruitShape: "Round",
                      fruitFlavor: "Sweet"
                  },
                  {
                      checked: false,
                      amount: 1,
                      machineCustomName: "Mint",
                      machineOS: "Linux Mint (Ubuntu/Debian)",
                      currentSlices: 4,
                      fruitColor: "Red",
                      fruitShape: "Round",
                      fruitFlavor: "Sweet"
                  },
                  {
                      checked: false,
                      amount: 1,
                      machineCustomName: "Arch Pentesting",
                      machineOS: "Arch Linux",
                      currentSlices: 1,
                      fruitColor: "Red",
                      fruitShape: "Round",
                      fruitFlavor: "Sweet"
                  }
              ]
          }
          delegate: DelegateChooser {
              DelegateChoice {
                  column: 0
                  delegate: CheckBox {
                      checked: model.display
                      onToggled: model.display = checked
                  }
              }
              DelegateChoice {
                  column: 1
                  delegate: TextField {
                      text: model.display
                      selectByMouse: true
                      implicitWidth: 240
                      onAccepted: model.display = text
                  }
              }
              DelegateChoice {
                  column: 2
                  delegate: SpinBox {
                      value: model.display
                      from: 1
                      to: 256
                      onValueModified: model.display = value
                  }
              }
              DelegateChoice {
                  column: 3
                  delegate: TextField {
                      text: model.display
                      selectByMouse: false
                      readOnly: true
                      implicitWidth: 200
                      onAccepted: model.display = text
                  }
              }
              DelegateChoice {
                  column: 4
                  delegate: TextField {
                      text: model.display
                      selectByMouse: false
                      readOnly: true
                      implicitWidth: 300
                      onAccepted: model.display = text
                    }
                }
              DelegateChoice {
                  column: 5
                  delegate: TextField {
                      text: model.display
                      selectByMouse: false
                      readOnly: true
                      implicitWidth: 300
                      onAccepted: model.display = text
                    }
                }
              DelegateChoice {
                  column: 6
                  delegate: TextField {
                      text: model.display
                      selectByMouse: false
                      readOnly: true
                      implicitWidth: 300
                      onAccepted: model.display = text
                    }
                }
              DelegateChoice {
                  column: 7
                  delegate: TextField {
                      text: model.display
                      selectByMouse: false
                      readOnly: true
                      implicitWidth: 300
                      onAccepted: model.display = text
                    }
                }
            }
        }
    }
}
