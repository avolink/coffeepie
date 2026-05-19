import sys
import subprocess
from PySide6.QtCore import QObject, Slot, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlContext

from api_client import CoffeePieApi
from translator import Translator


class MyMachine(QObject):
    def __init__(self, api):
        super().__init__()
        self._api = api
        api.streamReady.connect(self._on_stream_ready)

    @Slot()
    def mi_maquina_function(self):
        host_ip = "179.15.4.246"
        app_name = "desktop"
        self.stream_with_moonlight(host_ip, app_name)

    @Slot(str, str, str, str)
    def stream_machine(self, host_ip, app_name, resolution="1080", fps="60"):
        self.stream_with_moonlight(host_ip, app_name, resolution, fps)

    def _on_stream_ready(self, url, service_id, transport_id):
        if url.startswith("https://") or url.startswith("http://"):
            print(f"Launch URL: {url}")
        else:
            print(f"Stream ready for {service_id}/{transport_id}")

    def stream_with_moonlight(self, host_ip, app_name, resolution="1080", fps="60"):
        command = ["moonlight", "stream", host_ip, app_name, f"-{resolution}", "-fps", str(fps)]
        try:
            subprocess.run(command, check=True)
            print(f"Streaming {app_name} from {host_ip} at {resolution}p {fps}fps.")
        except subprocess.CalledProcessError as e:
            print(f"An error occurred while streaming: {e}")
        except FileNotFoundError:
            print("Moonlight is not installed or not found in your system's PATH.")


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    api = CoffeePieApi()
    machine = MyMachine(api)
    translator = Translator()

    context = engine.rootContext()
    context.setContextProperty("api", api)
    context.setContextProperty("myMachine", machine)
    context.setContextProperty("tr", translator)

    engine.load(QUrl.fromLocalFile("CoffeePieContent/App.qml"))
    if not engine.rootObjects():
        sys.exit(-1)

    root_window = engine.rootObjects()[0]
    root_window.setFlag(Qt.WindowStaysOnTopHint)
    root_window.show()

    sys.exit(app.exec())
