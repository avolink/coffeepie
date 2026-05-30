r"""Bre-B Instant Payment Backend.

Bre-B (Bre-Banking) is Colombia's real-time inter-bank payment system
operated by Banco de la República. It allows instant transfers 24/7/365
using payment keys: phone number, email, national ID, or random alphanumeric.

How it works for Coffee Pie:
  1. Coffee Pie registers a Bre-B key (e.g., phone: +57 300 000 0000)
  2. Customer initiates payment from their bank app using that key
  3. Payment clears instantly (< 30 seconds)
  4. Coffee Pie polls or receives webhook to confirm

API: Bre-B operates through participating banks. Each bank provides its own
API. This implementation uses a generic REST wrapper that works with
Bancolombia's Bre-B endpoint as the reference implementation.

Reference: https://www.banrep.gov.co/es/bre-b
"""

import hashlib
import hmac
import time
import requests
from typing import Optional
from datetime import datetime

from .base import PaymentBackend
from ..models import (
    PaymentRequest, PaymentResult, PaymentStatus, PaymentMethod,
    BreBPaymentKey, BreBTransfer,
)


class BreBBackend(PaymentBackend):
    """Bre-B instant payment backend.

    Environment variables:
        BREB_API_URL      — Your bank's Bre-B API endpoint
        BREB_API_KEY      — API key from your bank
        BREB_API_SECRET   — HMAC secret for request signing
        BREB_RECEIVER_KEY — Your registered Bre-B key (phone/email/doc)
        BREB_BANK_CODE    — Your bank code (Bancolombia = "001")
    """

    def __init__(self, api_url: str = None, api_key: str = None,
                 api_secret: str = None, receiver_key: str = None,
                 bank_code: str = None):
        import os
        self.api_url = api_url or os.getenv("BREB_API_URL", "https://api.bancolombia.com/breb/v1")
        self.api_key = api_key or os.getenv("BREB_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BREB_API_SECRET", "")
        self.receiver_key = receiver_key or os.getenv("BREB_RECEIVER_KEY", "")
        self.bank_code = bank_code or os.getenv("BREB_BANK_CODE", "001")
        self.timeout = 15

    @property
    def method(self) -> PaymentMethod:
        return PaymentMethod.BREB

    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        """Generate a Bre-B payment request.

        Returns the Bre-B key the customer should send money to.
        Unlike PSE, there's no redirect — the customer opens their
        own bank app and sends to our Bre-B key.
        """
        payload = {
            "receiver_key": self.receiver_key or request.breb_key,
            "receiver_bank": self.bank_code,
            "amount": request.amount_cop,
            "reference": request.reference,
            "description": request.description or f"Coffee Pie Credits — {request.amount_cr} Cr",
            "expires_at": request.expires_at,
            "webhook_url": request.webhook_url,
        }

        headers = self._signed_headers(payload)

        try:
            resp = requests.post(
                f"{self.api_url}/payment-requests",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            data = resp.json()
            breb_key = data.get("payment_key", self.receiver_key)

            return PaymentResult(
                success=True,
                transaction_id=data.get("request_id", request.reference),
                status=PaymentStatus.PENDING,
                method=PaymentMethod.BREB,
                amount_cop=request.amount_cop,
                amount_cr=request.amount_cr,
                gateway_response=f"Bre-B key: {breb_key} — send from your bank app",
                breb_key=breb_key,
            )
        except requests.RequestException as e:
            # Fallback: return static Bre-B key for manual payment
            return PaymentResult(
                success=True,
                transaction_id=request.reference,
                status=PaymentStatus.PENDING,
                method=PaymentMethod.BREB,
                amount_cop=request.amount_cop,
                amount_cr=request.amount_cr,
                gateway_response="Offline mode — use static Bre-B key",
                breb_key=self.receiver_key or "coffeepie@bancolombia",
            )

    def check_status(self, transaction_id: str) -> PaymentResult:
        """Poll Bre-B transfer status by transaction ID."""
        headers = self._signed_headers({})
        try:
            resp = requests.get(
                f"{self.api_url}/transfers/{transaction_id}",
                headers=headers,
                timeout=self.timeout,
            )
            data = resp.json()
            status = self._map_status(data.get("status", "PENDING"))

            return PaymentResult(
                success=(status == PaymentStatus.COMPLETED),
                transaction_id=transaction_id,
                status=status,
                method=PaymentMethod.BREB,
                amount_cop=data.get("amount", 0),
                amount_cr=data.get("amount", 0),
                gateway_response=data.get("message", ""),
                paid_at=data.get("completed_at", ""),
            )
        except requests.RequestException:
            return PaymentResult(
                success=False,
                transaction_id=transaction_id,
                status=PaymentStatus.PENDING,
                method=PaymentMethod.BREB,
                error_message="Could not connect to Bre-B API",
            )

    def handle_webhook(self, payload: dict) -> PaymentResult:
        """Process Bre-B webhook notification.

        Payload format (from bank):
        {
            "event": "transfer.received",
            "transaction_id": "BREB-20260530-XXXX",
            "sender_key": "3001234567",
            "receiver_key": "coffeepie@bancolombia",
            "amount": 50000,
            "reference": "CP-ABC12345",
            "timestamp": "2026-05-30T15:30:00Z",
            "signature": "hmac_sha256_signature"
        }
        """
        # Verify HMAC signature
        sig = payload.pop("signature", "")
        if sig and not self._verify_signature(payload, sig):
            return PaymentResult(success=False, error_message="Invalid webhook signature")

        return PaymentResult(
            success=True,
            transaction_id=payload.get("transaction_id", ""),
            status=PaymentStatus.COMPLETED,
            method=PaymentMethod.BREB,
            amount_cop=payload.get("amount", 0),
            amount_cr=payload.get("amount", 0),
            paid_at=payload.get("timestamp", ""),
        )

    def _signed_headers(self, payload: dict) -> dict:
        """Add HMAC authentication headers."""
        timestamp = str(int(time.time()))
        body = str(payload) if payload else ""
        signature = hmac.new(
            self.api_secret.encode(),
            f"{timestamp}{body}".encode(),
            hashlib.sha256,
        ).hexdigest()

        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Timestamp": timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json",
        }

    def _verify_signature(self, payload: dict, signature: str) -> bool:
        """Verify webhook HMAC signature."""
        expected = hmac.new(
            self.api_secret.encode(),
            str(payload).encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def _map_status(bank_status: str) -> PaymentStatus:
        mapping = {
            "COMPLETED": PaymentStatus.COMPLETED,
            "PROCESSING": PaymentStatus.PROCESSING,
            "PENDING": PaymentStatus.PENDING,
            "FAILED": PaymentStatus.FAILED,
            "EXPIRED": PaymentStatus.EXPIRED,
            "REVERSED": PaymentStatus.REFUNDED,
        }
        return mapping.get(bank_status.upper(), PaymentStatus.PENDING)

    @staticmethod
    def format_breb_key(key_type: str, key_value: str, bank: str = "Bancolombia") -> str:
        """Format a Bre-B key for display to the customer.

        Examples:
            Phone:  "3001234567@Bancolombia"
            Email:  "coffeepie@bancolombia"
            Doc:    "CC-1234567890"
            Random: "cp-recaudos-001"
        """
        if key_type == "phone":
            return f"{key_value}@{bank}"
        elif key_type == "email":
            return key_value
        elif key_type == "doc":
            return f"CC-{key_value}"
        else:
            return key_value
