from PySide6.QtCore import QObject, Signal, Slot, Property


class Translator(QObject):
    langChanged = Signal()

    @Slot(str, result=str)
    def tr(self, text):
        return text


class Api(QObject):
    loginSucceeded = Signal(str)
    loginFailed = Signal(str)
    purchaseCompleted = Signal(str)
    purchaseFailed = Signal(str)
    accountSaved = Signal(str)
    accountError = Signal(str)
    machinesLoaded = Signal(str)
    orchestratorsLoaded = Signal(str)
    turnCredentialsReady = Signal(str)
    balanceChanged = Signal()
    accountTypeChanged = Signal()
    adReady = Signal(str)
    adRewarded = Signal(str)
    adError = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logged_in = False
        self._balance = 0
        self._account_type = "FREE"
        self._orchestrator_urls = ["https://orquestador.coffeepie.co"]

    @Slot(result=bool)
    def isLoggedIn(self):
        return self._logged_in

    @Slot(str, str)
    def login(self, username, password):
        if username and password and len(username) >= 3 and len(password) >= 1:
            self._logged_in = True
            self.loginSucceeded.emit(username)
        else:
            self.loginFailed.emit("Credenciales invalidas")

    @Slot()
    def logout(self):
        self._logged_in = False

    @Slot()
    def fetchBalance(self):
        self.balanceChanged.emit()

    @Slot()
    def fetchMachines(self):
        self.machinesLoaded.emit("[]")

    @Slot(result=str)
    def getBalanceFormatted(self):
        return f"{self._balance} Cr"

    @Slot(result=str)
    def getAccountTypeText(self):
        return self._account_type

    @Slot(str)
    def purchasePackage(self, package_id):
        if package_id:
            self._balance += 0
            self.purchaseCompleted.emit("{}")

    @Slot(str)
    def setOrchestratorUrl(self, url):
        pass

    @Slot()
    def fetchOrchestrators(self):
        self.orchestratorsLoaded.emit("[]")

    @Slot()
    def fetchTurnCredentials(self):
        self.turnCredentialsReady.emit("{}")

    @Slot(result=str)
    def getNetworkTierLabel(self):
        return "Internet (Relay)"

    @Slot()
    def requestFreeCredits(self):
        self.adReady.emit("{}")

    @Slot()
    def claimAdReward(self):
        self._balance += 5
        self.balanceChanged.emit()
        self.adRewarded.emit("{}")

    @Property(str, constant=True)
    def orchestratorsJson(self):
        return "[]"


def create_stubs():
    return Api(), Translator()
