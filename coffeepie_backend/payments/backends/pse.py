"""PSE (Pagos Seguros en Línea) Payment Backend.

PSE is Colombia's ACH debit system. The user is redirected to their bank's
portal, authorizes the debit, and is returned to Coffee Pie.

Flow:
  1. Coffee Pie POSTs to PSE gateway with payment details
  2. PSE returns a redirect URL (bank selection page)
  3. User selects their bank, logs in, authorizes payment
  4. Bank debits account and redirects back to Coffee Pie
  5. PSE sends webhook confirmation (async, up to 24h)

Most widely used online payment method in Colombia. Required for
any serious e-commerce deployment.

Reference: https://www.pse.com.co
"""

import hashlib
import time
from typing import Optional

from .base import PaymentBackend
from ..models import PaymentRequest, PaymentResult, PaymentStatus, PaymentMethod


class PSEBackend(PaymentBackend):
    """PSE ACH debit backend.

    Environment variables:
        PSE_API_URL       — PSE gateway URL
        PSE_MERCHANT_ID   — Your PSE merchant ID
        PSE_API_KEY       — PSE API key
        PSE_TEST_MODE     — "true" for sandbox
    """

    # PSE bank codes (most commonly used)
    BANKS = {
        "bancolombia":  {"code": "1007", "name": "Bancolombia"},
        "davivienda":   {"code": "1052", "name": "Davivienda"},
        "bbva":         {"code": "1013", "name": "BBVA Colombia"},
        "bogota":       {"code": "1001", "name": "Banco de Bogota"},
        "occidente":    {"code": "1023", "name": "Banco de Occidente"},
        "popular":      {"code": "1002", "name": "Banco Popular"},
        "av_villas":    {"code": "1058", "name": "Banco AV Villas"},
        "caja_social":  {"code": "1032", "name": "Banco Caja Social"},
        "colpatria":    {"code": "1019", "name": "Scotiabank Colpatria"},
        "gnb":          {"code": "1072", "name": "GNB Sudameris"},
        "falabella":    {"code": "1062", "name": "Banco Falabella"},
        "pichincha":    {"code": "1065", "name": "Banco Pichincha"},
        "nequi":        {"code": "1507", "name": "Nequi"},
        "daviplata":    {"code": "1551", "name": "Daviplata"},
    }

    def __init__(self, api_url: str = None, merchant_id: str = None,
                 api_key: str = None, test_mode: bool = None):
        import os
        self.api_url = api_url or os.getenv("PSE_API_URL",
            "https://api.pse.com.co/v1")
        self.merchant_id = merchant_id or os.getenv("PSE_MERCHANT_ID", "")
        self.api_key = api_key or os.getenv("PSE_API_KEY", "")
        self.test_mode = test_mode or os.getenv("PSE_TEST_MODE", "true").lower() == "true"
        self.timeout = 30

    @property
    def method(self) -> PaymentMethod:
        return PaymentMethod.PSE

    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        """Initiate PSE payment. Returns redirect URL for bank selection."""
        payload = self._build_payload(request)

        if self.test_mode:
            return self._test_response(request)

        import requests
        try:
            resp = requests.post(
                f"{self.api_url}/transactions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            data = resp.json()

            return PaymentResult(
                success=True,
                transaction_id=data.get("transaction_id", request.reference),
                status=PaymentStatus.PENDING,
                method=PaymentMethod.PSE,
                amount_cop=request.amount_cop,
                amount_cr=request.amount_cr,
                redirect_url=data.get("redirect_url", ""),
                gateway_response="Redirecting to bank selection...",
            )
        except Exception as e:
            return PaymentResult(
                success=False,
                transaction_id=request.reference,
                status=PaymentStatus.FAILED,
                method=PaymentMethod.PSE,
                error_message=str(e),
            )

    def check_status(self, transaction_id: str) -> PaymentResult:
        """Poll PSE transaction status."""
        if self.test_mode:
            return self._test_status(transaction_id)

        import requests
        try:
            resp = requests.get(
                f"{self.api_url}/transactions/{transaction_id}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            data = resp.json()
            status = self._map_status(data.get("status", "PENDING"))

            return PaymentResult(
                success=(status == PaymentStatus.COMPLETED),
                transaction_id=transaction_id,
                status=status,
                method=PaymentMethod.PSE,
                amount_cop=data.get("amount", 0),
                gateway_response=data.get("message", ""),
                paid_at=data.get("completed_at", ""),
            )
        except Exception:
            return PaymentResult(
                success=False, transaction_id=transaction_id,
                status=PaymentStatus.PENDING, method=PaymentMethod.PSE,
                error_message="Status check unavailable",
            )

    def handle_webhook(self, payload: dict) -> PaymentResult:
        """Process PSE notification (POST from PSE to our webhook URL)."""
        tx_id = payload.get("transaction_id", "")
        status = self._map_status(payload.get("status", "PENDING"))

        return PaymentResult(
            success=(status == PaymentStatus.COMPLETED),
            transaction_id=tx_id,
            status=status,
            method=PaymentMethod.PSE,
            amount_cop=payload.get("amount", 0),
            paid_at=payload.get("completed_at", ""),
        )

    def _build_payload(self, request: PaymentRequest) -> dict:
        return {
            "merchant_id": self.merchant_id,
            "reference": request.reference,
            "amount": request.amount_cop,
            "currency": "COP",
            "description": request.description or f"Coffee Pie — {request.amount_cr} Creditos",
            "return_url": request.return_url,
            "cancel_url": request.cancel_url,
            "webhook_url": request.webhook_url,
            "customer": {
                "name": request.customer_name,
                "email": request.customer_email,
                "document_type": "CC",
                "document": request.customer_doc,
                "phone": request.customer_phone,
            },
            "expires_at": request.expires_at,
            "test": self.test_mode,
        }

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Merchant-ID": self.merchant_id,
        }

    def _test_response(self, request: PaymentRequest) -> PaymentResult:
        """Simulated PSE response for development/testing."""
        return PaymentResult(
            success=True,
            transaction_id=request.reference,
            status=PaymentStatus.PENDING,
            method=PaymentMethod.PSE,
            amount_cop=request.amount_cop,
            amount_cr=request.amount_cr,
            redirect_url=f"https://pse-test.coffeepie.co/select-bank?ref={request.reference}&amount={request.amount_cop}",
            gateway_response="TEST MODE — Select your bank to continue",
        )

    def _test_status(self, tx_id: str) -> PaymentResult:
        """Simulated PSE status check."""
        # In test mode, simulate completed after 5 seconds
        import time as _time
        tx_num = sum(ord(c) for c in tx_id) % 100
        is_done = tx_num < 70  # 70% chance of completion in test mode

        return PaymentResult(
            success=is_done,
            transaction_id=tx_id,
            status=PaymentStatus.COMPLETED if is_done else PaymentStatus.PENDING,
            method=PaymentMethod.PSE,
            amount_cop=50000,
            gateway_response="TEST MODE" if is_done else "TEST MODE — awaiting bank confirmation",
            paid_at=time.strftime("%Y-%m-%dT%H:%M:%SZ") if is_done else "",
        )

    @staticmethod
    def _map_status(pse_status: str) -> PaymentStatus:
        mapping = {
            "APPROVED": PaymentStatus.COMPLETED,
            "COMPLETED": PaymentStatus.COMPLETED,
            "PENDING": PaymentStatus.PENDING,
            "PROCESSING": PaymentStatus.PROCESSING,
            "REJECTED": PaymentStatus.FAILED,
            "FAILED": PaymentStatus.FAILED,
            "EXPIRED": PaymentStatus.EXPIRED,
            "REFUNDED": PaymentStatus.REFUNDED,
        }
        return mapping.get(pse_status.upper(), PaymentStatus.PENDING)
