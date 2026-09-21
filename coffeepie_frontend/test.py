import sys
import subprocess
from PyQt4.QtCore import QObject, pyqtSlot, QUrl, pyqtSignal
from PyQt4.QtQuick import QQuickView
from PyQt4.QtGui import QGuiApplication
from PyQt4.QtQml import QQmlContext
from PyQt4.QtQml import QQmlApplicationEngine
from PyQt4.QtCore import Qt
import requests
import uuid
import base64
import requests
import threading
import json  # Import json
from novncutils.chromeDriver import get_console_data, open_console_with_tokens

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "sunshine"
PASSWORD = "sunshine"

class MyMachine(QObject):

    vmStarted = pyqtSignal(bool)
    vmListUpdated = pyqtSignal(list)
    vmIpFetched = pyqtSignal(str)
    pinSent = pyqtSignal(bool, str)
    moonlightClosed = pyqtSignal()
    moonlightPaired = pyqtSignal(bool, str)
    vmCreated = pyqtSignal(bool)
    vm_counter = 1006

    def __init__(self):
        super(MyMachine, self).__init__()  # Use super(MyMachine, self).__init__()
        self.paired_hosts = set()

    def _run_in_thread(self, target_func, args_tuple):
        thread = threading.Thread(target=target_func, args=args_tuple)
        thread.daemon = True
        thread.start()

    def _execute_moonlight_pair(self, host_ip, command):
        try:
            process = subprocess.Popen(command)
            process.wait()
            if process.returncode == 0:
                print "Successfully initiated pairing with %s." % host_ip  # Use print statement
                self.paired_hosts.add(host_ip)
                self.moonlightPaired.emit(True, "Pairing initiated with %s. Check Moonlight for PIN entry." % host_ip)  # Use %s
            else:
                print "Failed to initiate pairing with %s. Moonlight process exited with code %s." % (host_ip, process.returncode)  # Use %s
                self.moonlightPaired.emit(False, "Failed to initiate pairing. Moonlight exit code: %s." % process.returncode)  # Use %s
        except Exception as e:
            print "An error occurred while trying to pair with %s: %s" % (host_ip, e)  # Use %s
            self.moonlightPaired.emit(False, "Error during pairing: %s" % e)  # Use %s

    def _execute_moonlight_stream(self, command, host_ip, app_name):
        try:
            process = subprocess.Popen(command)
            process.wait()
            print "Moonlight stream %s from %s finished. Exit code: %s" % (app_name, host_ip, process.returncode)  # Use %s
        except Exception as e:
            print "An error occurred while streaming: %s" % e  # Use %s
        finally:
            self.moonlightClosed.emit()

    @pyqtSlot(str)
    def pair_with_moonlight(self, host_ip):
        if not host_ip:
            print "Error: host_ip is empty. Cannot pair."  # Use print statement
            self.moonlightPaired.emit(False, "Host IP is empty.")
            return
        command = ["moonlight", "pair", host_ip]
        print "Attempting to pair with host: %s (non-blocking)" % host_ip  # Use %s
        self._run_in_thread(self._execute_moonlight_pair, (host_ip, command))

    @pyqtSlot(str, str, str)
    def sendPinToSunshine(self, ip, pin, client_name):
        sunshine_url = "https://%s:47990/api/pin" % ip  # Use %s
        try:
            credentials = "%s:%s" % (USERNAME, PASSWORD)  # Use %s
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                "Content-Type": "application/json",
                "Authorization": "Basic %s" % encoded_credentials  # Use %s
            }
            payload = {
                "pin": pin,
                "name": client_name
            }
            print sunshine_url  # Use print statement
            print "the payload", payload  # Use print statement
            response = requests.post(sunshine_url, data=json.dumps(payload), headers=headers, verify=False)  # Use json.dumps
            response.raise_for_status()
            return response.json()

            if response.status_code == 200:
                print "PIN sent successfully:", response.json()  # Use print statement
                self.pinSent.emit(True, "PIN sent successfully")
            else:
                print "Failed to send PIN: %s, %s" % (response.status_code, response.text)  # Use %s
                self.pinSent.emit(False, "Failed to send PIN: %s" % response.text)  # Use %s
        except Exception as e:
            print "Error sending PIN: %s" % e  # Use %s
            self.pinSent.emit(False, "Error: %s" % e)  # Use %s

    @pyqtSlot(str, result=bool)
    def isHostPaired(self, host_ip):
        return host_ip in self.paired_hosts

    @pyqtSlot(str, str)
    def fetchVmIp(self, node, vmId):
        if not vmId:
            print "Error: vmId is empty. Cannot fetch IP address."  # Use print statement
            self.vmIpFetched.emit("")
            return
        url = "%s/nodes/%s/vms/%s/ip" % (BASE_URL, node, vmId)  # Use %s
        try:
            print url  # Use print statement
            print "Fetching IP address for VM %s on node %s..." % (vmId, node)  # Use %s
            response = requests.get(url, headers={"accept": "application/json"})
            if response.status_code == 200:
                data = response.json()
                ip_addresses = data.get("ip_addresses", [])
                if ip_addresses:
                    ip_address = ip_addresses[0]
                    print "IP address for VM %s: %s" % (vmId, ip_address)  # Use %s
                    self.vmIpFetched.emit(ip_address)
                else:
                    print "No IP addresses found for VM %s." % vmId  # Use %s
                    self.vmIpFetched.emit("")
            else:
                print "Failed to fetch IP address for VM %s: %s, %s" % (vmId, response.status_code, response.text)  # Use %s
                self.vmIpFetched.emit("")
        except Exception as e:
            print "Error fetching IP address for VM %s: %s" % (vmId, e)  # Use %s
            self.vmIpFetched.emit("")

    @pyqtSlot(str, str)
    def startVM(self, node, vmId):
        url = "%s/nodes/%s/vms/%s/start" % (BASE_URL, node, vmId)  # Use %s
        try:
            print "Starting VM %s on node %s..." % (vmId, node)  # Use %s
            response = requests.post(url, headers={"accept": "application/json"}, data="")
            if response.status_code == 200:
                print "VM %s started successfully." % vmId  # Use %s
                self.vmStarted.emit(True)
            else:
                print "Failed to start VM %s: %s, %s" % (vmId, response.status_code, response.text)  # Use %s
                self.vmStarted.emit(False)
        except Exception as e:
            print "Error starting VM %s: %s" % (vmId, e)  # Use %s
            self.vmStarted.emit(False)

    @pyqtSlot(str)
    def fetchVMList(self, node):
        url = "%s/nodes/%s/vms" % (BASE_URL, node)  # Use %s
        try:
            response = requests.get(url)
            if response.status_code == 200:
                vms = response.json().get("vms", [])
                print vms  # Use print statement
                numeric_vms = [vm for vm in vms if vm.isdigit()]
                print numeric_vms  # Use print statement

                if numeric_vms:
                    max_vm = max(int(vm) for vm in numeric_vms)
                    MyMachine.vm_counter = max_vm + 1
                else:
                    MyMachine.vm_counter = 1000
                self.vmListUpdated.emit(numeric_vms)
            else:
                print "Failed to fetch VM list: %s, %s" % (response.status_code, response.text)  # Use %s
                self.vmListUpdated.emit([])
        except Exception as e:
            print "Error fetching VM list: %s" % e  # Use %s
            self.vmListUpdated.emit([])

    @pyqtSlot()
    def mi_maquina_function(self):
        host_ip = "179.15.4.246"
        app_name = "desktop"
        resolution = "1080"
        fps = "60"

        print "Starting stream for %s at %sp %sfps." % (app_name, resolution, fps)  # Use %s
        self.stream_with_moonlight(host_ip, app_name, resolution, fps)

    @pyqtSlot(str, str, str, str)
    def stream_with_moonlight(self, host_ip, app_name, resolution="1080", fps="60"):
        command = ["moonlight", "stream", host_ip, app_name, "-%s" % resolution, "-fps", fps]  # Use %s
        print "Attempting to stream %s from %s (non-blocking)" % (app_name, host_ip)  # Use %s
        self._run_in_thread(self._execute_moonlight_stream, (command, host_ip, app_name))

    @pyqtSlot(str, str, str)
    def createAndStreamVM(self, template_name, node, base_name):
        clone_url = "%s/clone-by-name" % BASE_URL  # Use %s
        MyMachine.vm_counter += 1
        new_vm_id = MyMachine.vm_counter
        new_vm_name = str(new_vm_id)

        clone_payload = {
            "source_name": template_name,
            "newid": new_vm_id,
            "name": new_vm_name,
            "node": node,
            "storage": "local-lvm",
            "full": 0
        }
        print clone_payload  # Use print statement
        try:
            clone_response = requests.post(clone_url, data=json.dumps(clone_payload))  # Use json.dumps
            if clone_response.status_code == 200:
                print "VM '%s' cloning initiated successfully." % new_vm_id  # Use %s
                self.vmCreated.emit(True)
            else:
                print "Failed to initiate VM cloning: %s, %s" % (clone_response.status_code, clone_response.text)  # Use %s
                self.vmCreated.emit(False)
        except Exception as e:
            print "Error during VM creation: %s" % e  # Use %s
            self.vmCreated.emit(False)

    @pyqtSlot(str, int, str)
    def openConsole(self, node, vmid, vmname):
        try:
            print "Fetching console data for VM %s on node %s with name %s..." % (vmid, node, vmname)  # Use %s
            console_url, ticket, csrf_token = get_console_data(node, vmid, vmname)
            print "Console data fetched successfully. Opening console at %s..." % console_url  # Use %s
            open_console_with_tokens(console_url, ticket, csrf_token)
        except Exception as e:
            print "Error opening console for VM %s: %s" % (vmid, e)  # Use %s

    @pyqtSlot(str)
    def updateIconSource(self, new_icon_source):
        self.iconSourceChanged.emit(new_icon_source)

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    context = engine.rootContext()
    machine = MyMachine()
    context.setContextProperty("myMachine", machine)

    engine.load(QUrl.fromLocalFile("CoffeePieContent/Login_Screen.qml"))
    if not engine.rootObjects():
        sys.exit(-1)

    root_window = engine.rootObjects()[0]
    if isinstance(root_window, QQuickView):
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Window
        root_window.setFlags(flags)
        root_window.showFullScreen()

    root_window.show()
    sys.exit(app.exec_())