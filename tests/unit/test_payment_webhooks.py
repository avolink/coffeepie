"""Payment webhooks must fail closed: no valid signature, no payment.

Run from the repo root:
  python3 -m unittest tests.unit.test_payment_webhooks
"""
import hashlib
import hmac
import json
import unittest

from coffeepie_backend.payments.backends.bancolombia import BancolombiaQRBackend
from coffeepie_backend.payments.backends.breb import BreBBackend
from coffeepie_backend.payments.backends.pse import PSEBackend

SECRET = "test-secret"


class PSEWebhook(unittest.TestCase):
    def backend(self, secret=SECRET):
        b = PSEBackend()
        b.webhook_secret = secret
        return b

    @staticmethod
    def signed(payload, secret=SECRET):
        msg = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return {**payload, "signature": hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()}

    def test_valid_signature_is_accepted(self):
        r = self.backend().handle_webhook(self.signed({"transaction_id": "T1", "status": "APPROVED", "amount": 1000}))
        self.assertEqual(r.transaction_id, "T1")

    def test_missing_signature_is_rejected(self):
        r = self.backend().handle_webhook({"transaction_id": "T1", "status": "APPROVED", "amount": 1000})
        self.assertFalse(r.success)
        self.assertEqual(r.error_message, "Invalid webhook signature")

    def test_wrong_signature_is_rejected(self):
        p = self.signed({"transaction_id": "T1", "status": "APPROVED", "amount": 1000})
        p["amount"] = 999999
        self.assertFalse(self.backend().handle_webhook(p).success)

    def test_unset_secret_rejects_everything(self):
        p = self.signed({"transaction_id": "T1", "status": "APPROVED", "amount": 1000}, secret="")
        self.assertFalse(self.backend(secret="").handle_webhook(p).success)

    def test_caller_payload_is_not_mutated(self):
        p = self.signed({"transaction_id": "T1", "status": "APPROVED", "amount": 1000})
        self.backend().handle_webhook(p)
        self.assertIn("signature", p)


class BreBWebhook(unittest.TestCase):
    def backend(self, secret=SECRET):
        b = BreBBackend()
        b.api_secret = secret
        return b

    def test_valid_signature_is_accepted(self):
        b = self.backend()
        body = {"transaction_id": "B1", "amount": 5000}
        sig = hmac.new(SECRET.encode(), str(body).encode(), hashlib.sha256).hexdigest()
        self.assertTrue(b.handle_webhook({**body, "signature": sig}).success)

    def test_missing_signature_is_rejected(self):
        self.assertFalse(self.backend().handle_webhook({"transaction_id": "B1", "amount": 5000}).success)

    def test_unset_secret_rejects_everything(self):
        b = self.backend(secret="")
        body = {"transaction_id": "B1", "amount": 5000}
        sig = hmac.new(b"", str(body).encode(), hashlib.sha256).hexdigest()
        self.assertFalse(b.handle_webhook({**body, "signature": sig}).success)


class BancolombiaWebhook(unittest.TestCase):
    def backend(self, secret=SECRET):
        b = BancolombiaQRBackend()
        b.api_secret = secret
        return b

    def test_valid_signature_is_accepted(self):
        body = {"transaction_id": "Q1", "estado": "APROBADO", "monto": 100}
        firma = hashlib.sha256((str(body) + SECRET).encode()).hexdigest()
        self.assertTrue(self.backend().handle_webhook({**body, "firma": firma}).success)

    def test_missing_signature_is_rejected(self):
        r = self.backend().handle_webhook({"transaction_id": "Q1", "estado": "APROBADO", "monto": 100})
        self.assertFalse(r.success)
        self.assertEqual(r.error_message, "Invalid webhook signature")

    def test_unset_secret_rejects_everything(self):
        b = self.backend(secret="")
        body = {"transaction_id": "Q1", "estado": "APROBADO"}
        firma = hashlib.sha256(str(body).encode()).hexdigest()
        self.assertFalse(b.handle_webhook({**body, "firma": firma}).success)


if __name__ == "__main__":
    unittest.main()
