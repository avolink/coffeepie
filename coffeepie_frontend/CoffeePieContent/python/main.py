import os
import sys
import subprocess
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, pyqtSignal, pyqtProperty
from PyQt5.QtQuick import QQuickView
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlContext
from PyQt5.QtQml import QQmlApplicationEngine
from PyQt5.QtCore import Qt
import requests  
import uuid
import base64
import requests
import threading # Import threading
from novncutils.chromeDriver import get_console_data, open_console_with_tokens
from auth.authutiles import login_user, create_user
from vms.vmsutilities import fetch_my_vms, get_console_url, start_my_vm, stop_vm, reboot_vm, clone_vm, delete_vm, shutdown_vm,get_vm_status,clone_vm_with_specs,create_snapshot
from vms.nodePx import fetch_vm_ip, start_vm, fetch_vm_list
from user.userutilities import get_my_credits, get_my_user


#BASE_URL = "http://127.0.0.1:8000" 
#host = os.environ.get("API_HOST", "127.0.0.1")
#BASE_URL = f"http://{host}:8000"
BASE_URL = "https://3e33-181-132-118-30.ngrok-free.app"

USERNAME = "sunshine"  # Replace with your Sunshine username
PASSWORD = "sunshine"  # Replace with your Sunshine password
class MyMachine(QObject):
    reloadRequested = pyqtSignal()
    vmStarted = pyqtSignal(bool)  # Signal to notify QML when the VM is started

    vmListUpdated = pyqtSignal(list)
    
    vmIpFetched = pyqtSignal(str)  
     # Signal to send the VM list to QML
    pinSent = pyqtSignal(bool, str)  # Signal to notify QML about the result of the PIN submission
    
    moonlightClosed = pyqtSignal() 
    moonlightPaired = pyqtSignal(bool, str) # Signal for pairing result

    vmCreated = pyqtSignal(bool)
    userCreated = pyqtSignal(bool, str)  # (success, message)
    vm_counter = 1006 

    unauthorized = pyqtSignal()
    loginSuccess = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.paired_hosts = set()
        self._userToken = ""
        self._selectedVmId = ""
        self._vmCredits = ""

    @pyqtProperty(str)
    def userToken(self):
        return self._userToken

    @userToken.setter
    def userToken(self, value):
        self._userToken = value

    @pyqtProperty(str)
    def selectedVmId(self):
        return self._selectedVmId

    @selectedVmId.setter
    def selectedVmId(self, value):
        self._selectedVmId = value

    @pyqtProperty(str)
    def vmCredits(self):
        return self._vmCredits

    @vmCredits.setter
    def vmCredits(self, value):
        self._vmCredits = value

    def _run_in_thread(self, target_func, args_tuple):
        thread = threading.Thread(target=target_func, args=args_tuple)
        thread.daemon = True
        thread.start()

   



    




    @pyqtSlot(str, str)
    def fetchVmIp(self, node, vmId):
        """
        Fetches the IP address of a VM using the provided node and VM ID.

        Args:
            node (str): The node where the VM is located.
            vmId (str): The ID of the VM to fetch the IP address for.
        """

        if not vmId:
         print("Error: vmId is empty. Cannot fetch IP address.")
         self.vmIpFetched.emit("")  # Emit an empty string if vmId is invalid
         return
        ip = fetch_vm_ip(node, vmId, base_url=BASE_URL)
        self.vmIpFetched.emit(ip)

    @pyqtSlot(str, str)
    def startVM(self, token, vmId):
        """
        Starts a VM using the provided node and VM ID.

        Args:
            node (str): The node where the VM is located.
            vmId (str): The ID of the VM to start.
        """
        success = start_my_vm(token, vmId, base_url=BASE_URL)
        self.vmStarted.emit(success)

    @pyqtSlot(str)
    def fetchVMList(self, node):
        """
        Fetches the list of VMs from the endpoint and filters numeric IDs.

        Args:
            node (str): The node to fetch VMs from.
        """
        numeric_vms = fetch_vm_list(node, base_url=BASE_URL)
        # Update vm_counter to be max of numeric_vms + 1
        if numeric_vms:
            max_vm = max(int(vm) for vm in numeric_vms)
            MyMachine.vm_counter = max_vm + 1
        else:
            MyMachine.vm_counter = 1000  # or any default starting va
        self.vmListUpdated.emit(numeric_vms)  # Emit the filtered list to QML
  






    @pyqtSlot(str, int, str)
    def openConsole(self, node, vmid, vmname):
        """
        Opens the console for a VM using the provided node, VM ID, and VM name.

        Args:
            node (str): The node where the VM is located.
            vmid (int): The ID of the VM.
            vmname (str): The name of the VM.
        """
        try:
            print(f"Fetching console data for VM {vmid} on node {node} with name {vmname}...")
            console_url, ticket, csrf_token = get_console_data(node, vmid, vmname)
            print(f"Console data fetched successfully. Opening console at {console_url}...")
            open_console_with_tokens(console_url, ticket, csrf_token)
        except Exception as e:
            print(f"Error opening console for VM {vmid}: {e}")
    @pyqtSlot(str)
    def updateIconSource(self, new_icon_source):
        # Emit a signal to update the icon source in QML
        self.iconSourceChanged.emit(new_icon_source)

    @pyqtSlot('QVariant', result=bool)
    def createUser(self, userData):
        """
        Receives user data from QML and creates a user via the API.
        Args:
            userData (dict or QJSValue): Dictionary with user fields (name, email, etc.)
        Returns:
            bool: True if user created successfully, False otherwise.
        """
        print(userData)
        if hasattr(userData, 'toVariant'):
            userData = userData.toVariant()
        success, message = create_user(userData, base_url=BASE_URL)
        self.userCreated.emit(success, message)
        return success

    @pyqtSlot(str, str, str, result='QVariant')
    def loginUser(self, email, password, terminalID):
        """
        Calls the login_user utility to authenticate a user.
        Args:
            email (str): User's email.
            password (str): User's password.
            terminalID (str): Terminal identifier.
        Returns:
            dict or None: The response from the backend, or None if failed.
        """
        result = login_user(email, password, terminalID, base_url=BASE_URL)
        if result and isinstance(result, dict) and result.get('access_token'):
            self.userToken = result['access_token']
            self.loginSuccess.emit()
        return result

    @pyqtSlot(str, result='QVariant')
    def fetchMyVMs(self, token):
        """
        Fetches the VMs for the current user using the provided access token.
        Args:
            token (str): The access token (JWT).
        Returns:
            dict or None: The response from the backend, or None if failed.
        """
        result = fetch_my_vms(token, base_url=BASE_URL)
        if (isinstance(result, dict) and result.get('status_code', None) == 401) or (isinstance(result, dict) and 'Unauthorized' in str(result.get('detail', ''))):
            self.unauthorized.emit()
        return result
    
    @pyqtSlot(str, str, result='QVariant')
    def getConsoleUrl(self, token, id):
        """
        Fetch the console URL and tokens for a VM using the user's access token.
        Returns a dict with success and detail for errors.
        """
        result = get_console_url(token, id, base_url=BASE_URL)
        if (isinstance(result, dict) and result.get('status_code', None) == 401) or (isinstance(result, dict) and 'Unauthorized' in str(result.get('detail', ''))):
            self.unauthorized.emit()
        return result
       
    @pyqtSlot(str, str)
    def stopVM(self, token, vmId):
        """
        Stops a VM using the provided token and VM ID.
        """
        result = stop_vm(token, vmId, base_url=BASE_URL)
        if (isinstance(result, dict) and result.get('status_code', None) == 401) or (isinstance(result, dict) and 'Unauthorized' in str(result.get('detail', ''))):
            self.unauthorized.emit()
        return result
    
    @pyqtSlot(str, str)
    def rebootVM(self, token, vmId):
        """
        Reboots a VM using the provided token and VM ID.
        """
        result = reboot_vm(token, vmId, base_url=BASE_URL)
        if (isinstance(result, dict) and result.get('status_code', None) == 401) or (isinstance(result, dict) and 'Unauthorized' in str(result.get('detail', ''))):
            self.unauthorized.emit()
        return result
    
    @pyqtSlot(str, str)
    def cloneVM(self, token, vmId):
        """
        Clones a VM using the provided token and VM ID.
        """
        result = clone_vm(token, vmId, base_url=BASE_URL)
        if (isinstance(result, dict) and result.get('status_code', None) == 401) or (isinstance(result, dict) and 'Unauthorized' in str(result.get('detail', ''))):
            self.unauthorized.emit()
        return result
    
    @pyqtSlot(str, str)
    def deleteVM(self, token, vmId):
        """
        Deletes a VM using the provided token and VM ID.
        """
        result = delete_vm(token, vmId, base_url=BASE_URL)
        if (isinstance(result, dict) and result.get('status_code', None) == 401) or (isinstance(result, dict) and 'Unauthorized' in str(result.get('detail', ''))):
            self.unauthorized.emit()
        return result
    
    @pyqtSlot(str, result='QVariant')
    def getMyCredits(self, token):
        """
        Gets the user's credits using the provided token.
        """
        result = get_my_credits(token, base_url=BASE_URL)
        if (isinstance(result, dict) and result.get('status_code', None) == 401) or (isinstance(result, dict) and 'Unauthorized' in str(result.get('detail', ''))):
            self.unauthorized.emit()
        return result
    
    @pyqtSlot(str, str, result='QVariant')
    def getVMStatus(self, token, vmid):
    
        result = get_vm_status(token, vmid, base_url=BASE_URL)
        if (isinstance(result, dict) and result.get('status_code', None) ==401) or (isinstance(result, dict) and 'Unauthorized' in str(result.get('detail', ''))):
             self.unauthorized.emit()
        return result
        


    @pyqtSlot()
    def requestReload(self):
        self.reloadRequested.emit()

    @pyqtSlot(str, str)
    def shutdownVM(self, token, vmId):
        """
        Shuts down a VM using the provided token and VM ID.
        """
        result = shutdown_vm(token, vmId, base_url=BASE_URL)
        if (isinstance(result, dict) and result.get('status_code', None) == 401) or (isinstance(result, dict) and 'Unauthorized' in str(result.get('detail', ''))):
            self.unauthorized.emit()
        return result
        
    @pyqtSlot(str, result='QVariant')
    def getMyUserName(self, token):
       """
        Fetches the current user's name using the provided access token.
        Returns a dict with 'name' or error detail.
       """
       result = get_my_user(token, base_url=BASE_URL)
       if isinstance(result, dict) and "name" in result:
           return {"name": result["name"]}
       elif isinstance(result, dict) and "detail" in result:
           return {"error": result["detail"]}
       else:
           return {"error": "No se pudo obtener el nombre de usuario."}
       
    @pyqtSlot(str, 'QVariant', result='QVariant')
    def cloneVMWithSpecs(self, token, specs):
        """
        Clones a VM with custom specs using the provided token and specs dictionary.
        Returns the backend response or error detail.
        
        """
        print(f"Cloning VM with specs: {specs}")
        # If specs is a QJSValue from QML, convert to Python dict
        if hasattr(specs, 'toVariant'):
            specs = specs.toVariant()
        result = clone_vm_with_specs(token, specs, base_url=BASE_URL)
        if isinstance(result, dict) and result.get('status_code', None) == 401:
            self.unauthorized.emit()
        return result

    @pyqtSlot(str, str, str, result='QVariant')
    def createSnapshot(self, token, vm_id, description):
        """
        Creates a snapshot for a VM using the provided token, VM ID, and description.
        Returns the backend response or error detail.
        """
        result = create_snapshot(token, vm_id, description, base_url=BASE_URL)
        if isinstance(result, dict) and result.get('status_code', None) == 401:
            self.unauthorized.emit()
        return result


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
     # Use QQmlApplicationEngine instead of QQuickView
    engine = QQmlApplicationEngine()

    # Add import path for QML singletons (GlobalToken)


    # Expose the MyMachine object to QML
    context = engine.rootContext()
    machine = MyMachine()
    context.setContextProperty("myMachine", machine)

    # Load the QML file
    engine.load(QUrl.fromLocalFile("CoffeePieContent/Login_Screen.qml"))
    if not engine.rootObjects():
        sys.exit(-1)
# Get the root window and set it to always stay on top
    root_window = engine.rootObjects()[0]
    # Convert the QQuickWindow to QWindow to set window flags
     # Set window flags to keep the window on top (directly on the QQuickWindow)
   #Convert to QQuickView if it's not already (QQuickView supports window flags)
    if isinstance(root_window, QQuickView):
        # Set window flags to keep the window on top
        #root_window.setWindowFlags(Qt.WindowStaysOnTopHint)
        #root_window.setWindowFlags(Qt.WindowFullScreen)

        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Window
        root_window.setFlags(flags)
        root_window.showFullScreen()
    # Show the window
    root_window.show()

    sys.exit(app.exec_())