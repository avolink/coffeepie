"""
Coffee Pie REST API client for QML frontend.
Communicates with the Coffee Pie Orchestrator (OpenUDS-based).
"""
import json
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

from PySide6.QtCore import QObject, Signal, Slot, Property

logger = logging.getLogger(__name__)

DEFAULT_ORCHESTRATOR_URL = "https://orquestador.coffeepie.co"


class CoffeePieApi(QObject):
    balanceChanged = Signal()
    accountTypeChanged = Signal()
    loginSucceeded = Signal(str)
    loginFailed = Signal(str)
    purchaseCompleted = Signal(str)
    purchaseFailed = Signal(str)
    accountSaved = Signal(str)
    accountError = Signal(str)
    machinesLoaded = Signal(str)
    streamReady = Signal(str, str, str)
    orchestratorsLoaded = Signal(str)
    turnCredentialsReady = Signal(str)
    deviceRegistered = Signal(str)
    adReady = Signal(str)
    adRewarded = Signal(str)
    adError = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._orchestrator_url = DEFAULT_ORCHESTRATOR_URL
        self._orchestrator_urls = [DEFAULT_ORCHESTRATOR_URL]
        self._auth_token = ""
        self._username = ""
        self._balance = 0
        self._account_type = "FREE"
        self._lifetime_purchased = 0
        self._lifetime_consumed = 0
        self._lifetime_ad_rewards = 0
        self._machines_json = "[]"
        self._network_tier = "L3"
        self._current_region = ""
        self._package_name_cache = {}

    def _base_url(self):
        return self._orchestrator_url.rstrip("/") + "/uds/rest"

    def _request(self, method, path, data=None):
        url = self._base_url() + "/" + path.lstrip("/")
        body = None
        if data and method.upper() in ("POST", "PUT"):
            body = urlencode(data).encode("utf-8") if isinstance(data, dict) else data.encode("utf-8")
        req = Request(url, data=body, method=method.upper())
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Accept", "application/json")
        if self._auth_token:
            req.add_header("X-Auth-Token", self._auth_token)
        try:
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            try:
                error_body = json.loads(e.read().decode("utf-8"))
                return {"error": str(e.code), "detail": error_body}
            except Exception:
                return {"error": str(e.code)}
        except URLError as e:
            return {"error": f"Connection failed: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}

    @property
    def balance(self):
        return self._balance

    @property
    def accountType(self):
        return self._account_type

    @property
    def machinesJson(self):
        return self._machines_json

    @property
    def networkTier(self):
        return self._network_tier

    @property
    def orchestratorsJson(self):
        return json.dumps(self._orchestrator_urls)

    @Slot(str)
    def setOrchestratorUrl(self, url):
        if url:
            self._orchestrator_url = url
            if url not in self._orchestrator_urls:
                self._orchestrator_urls.insert(0, url)

    @Slot(str, str)
    def login(self, username, password):
        if not username or not password:
            self.loginFailed.emit("Ingrese usuario y contraseña")
            return
        self._username = username
        resp = self._request("POST", "auth/login", {
            "username": username,
            "password": password,
            "auth_id": "1",
        })
        if isinstance(resp, list) and len(resp) > 0:
            resp = resp[0]
        if resp.get("result") == "ok" and resp.get("auth"):
            self._auth_token = resp["auth"]
            self.loginSucceeded.emit(username)
        else:
            error_msg = resp.get("error", resp.get("detail", "Credenciales inválidas"))
            if isinstance(error_msg, dict):
                error_msg = str(error_msg)
            self.loginFailed.emit(str(error_msg))

    @Slot()
    def fetchBalance(self):
        resp = self._request("GET", "coffeepie/credits/balance")
        if "error" in resp:
            return
        self._balance = resp.get("balance", 0)
        self._lifetime_purchased = resp.get("lifetime_purchased", 0)
        self._lifetime_consumed = resp.get("lifetime_consumed", 0)
        self._lifetime_ad_rewards = resp.get("lifetime_ad_rewards", 0)
        if self._lifetime_purchased > 0:
            self._account_type = "PAGO"
        self.balanceChanged.emit()
        self.accountTypeChanged.emit()

    @Slot()
    def fetchMachines(self):
        resp = self._request("GET", "coffeepie/client/services")
        if "error" not in resp:
            self._machines_json = json.dumps(resp)
            self.machinesLoaded.emit(self._machines_json)
        else:
            self._machines_json = "[]"
            self.machinesLoaded.emit("[]")

    @Slot(str)
    def purchasePackage(self, package_id):
        resp = self._request("POST", "coffeepie/credits/purchase", {"package_id": package_id})
        if "error" in resp:
            self.purchaseFailed.emit(str(resp.get("error", resp.get("detail", "Error al comprar créditos"))))
        else:
            self._balance = resp.get("balance", self._balance)
            self._lifetime_purchased = resp.get("lifetime_purchased", self._lifetime_purchased)
            self._account_type = "PAGO"
            self.balanceChanged.emit()
            self.accountTypeChanged.emit()
            self.purchaseCompleted.emit(json.dumps(resp))

    @Slot(str, str)
    def requestStream(self, service_id, transport_id):
        resp = self._request("GET", f"webapi/action/{service_id}/enable/{transport_id}")
        if isinstance(resp, dict) and resp.get("url"):
            self.streamReady.emit(resp["url"], service_id, transport_id)
        elif isinstance(resp, dict) and resp.get("result") == "ok":
            self.streamReady.emit("ok", service_id, transport_id)
        else:
            self.streamReady.emit("", service_id, transport_id)

    @Slot(str, str, str, str, str, str, str, str, str)
    def saveAccount(self, org_name, legal_name, tax_id, invoice_email,
                    billing_contact, billing_phone, fiscal_address,
                    tech_contact, tech_email):
        resp = self._request("POST", "coffeepie/credits/account", {
            "org_name": org_name, "legal_name": legal_name,
            "tax_id": tax_id, "invoice_email": invoice_email,
            "billing_contact": billing_contact, "billing_phone": billing_phone,
            "fiscal_address": fiscal_address, "tech_contact": tech_contact,
            "tech_email": tech_email,
        })
        if "error" in resp:
            self.accountError.emit(str(resp.get("error", "Error al guardar")))
        else:
            self.accountSaved.emit("Datos guardados correctamente")

    @Slot(result=str)
    def getBalanceFormatted(self):
        if self._balance >= 1_000_000:
            return f"{self._balance / 1_000_000:.1f}M Cr"
        elif self._balance >= 1_000:
            return f"{self._balance:,} Cr"
        return f"{self._balance} Cr"

    @Slot(result=str)
    def getAccountTypeText(self):
        types = {
            "FREE": "GRATUITA",
            "PAGO": "PAGO",
            "FLEX": "FLEX",
        }
        return types.get(self._account_type, self._account_type)

    @Slot()
    def fetchOrchestrators(self):
        resp = self._request("GET", "coffeepie/orchestrators")
        if "error" not in resp:
            urls = [r["url"] for r in resp if r.get("url")]
            if urls:
                self._orchestrator_urls = urls
                self._current_region = resp[0].get("region", "") if resp else ""
            self.orchestratorsLoaded.emit(json.dumps(resp))

    @Slot()
    def fetchTurnCredentials(self):
        resp = self._request("POST", "coffeepie/turn/credentials", {"region": self._current_region or "CO-01"})
        if resp.get("available"):
            self._network_tier = resp.get("network_tier", "L3")
            self.turnCredentialsReady.emit(json.dumps(resp))
        else:
            self.turnCredentialsReady.emit(json.dumps({"available": False}))

    @Slot(str, str, str, str, str)
    def registerDevice(self, mac, serial, model, manufacturer, public_key):
        resp = self._request("POST", "coffeepie/device/register", {
            "mac_address": mac, "serial_number": serial,
            "model_name": model, "manufacturer": manufacturer,
            "public_key": public_key,
        })
        if resp.get("device_id"):
            self._network_tier = resp.get("network_tier", "L3")
            self.deviceRegistered.emit(json.dumps(resp))
        else:
            self.deviceRegistered.emit(json.dumps({"error": str(resp.get("error", "Registration failed"))}))

    @Slot(str, str, str)
    def startNatSession(self, mac, local_ip, local_port):
        resp = self._request("POST", "coffeepie/session/start", {
            "mac_address": mac, "local_ip": local_ip,
            "local_port": local_port,
        })
        return json.dumps(resp)

    @Slot(result=str)
    def getNetworkTierLabel(self):
        labels = {"L2": "Privada (Certificada)", "L3": "Internet (Relay)", "L4": "WebRTC (Fallback)"}
        return labels.get(self._network_tier, self._network_tier)

    @Slot()
    def requestFreeCredits(self):
        user_context = {
            "demographics": {
                "languages": [{"code": "es", "is_preferred": True}],
                "location": {"country": "Colombia"},
            },
        }
        resp = self._request("POST", "coffeepie/ads/ad/request", {
            "request_id": "",
            "user_context": user_context,
        })
        if resp.get("status") == "matched":
            self._ad_bid_id = resp.get("campaign_id", "")
            self.adReady.emit(json.dumps(resp))
        else:
            self.adError.emit(resp.get("message", "No ads available"))

    @Slot()
    def claimAdReward(self):
        if not getattr(self, "_ad_bid_id", ""):
            self.adError.emit("No active ad to claim")
            return
        resp = self._request("POST", "coffeepie/credits/ad/reward", {"bid_id": self._ad_bid_id})
        if resp.get("status") == "ok":
            self._balance = resp.get("balance", self._balance)
            self._lifetime_ad_rewards = self._lifetime_ad_rewards or 0
            self.balanceChanged.emit()
            self.adRewarded.emit(json.dumps(resp))
        else:
            self.adError.emit(str(resp.get("error", resp.get("detail", "Failed to claim reward"))))

