"""Coffee Pie Payment Service.

Orchestrates payment flows across all backends.
Handles Bre-B, PSE, Bancolombia QR, and COFP token burns uniformly.
"""

import os
import logging
from typing import Optional, Dict, Type

from .models import (
    PaymentRequest, PaymentResult, PaymentStatus, PaymentMethod,
    Invoice, calculate_iva, cop_to_credits, generate_cufe,
)
from .backends.base import PaymentBackend
from .backends.pse import PSEBackend
from .backends.breb import BreBBackend
from .backends.bancolombia import BancolombiaQRBackend

logger = logging.getLogger("coffeepie.payments")

BACKEND_REGISTRY: Dict[PaymentMethod, Type[PaymentBackend]] = {
    PaymentMethod.PSE: PSEBackend,
    PaymentMethod.BREB: BreBBackend,
    PaymentMethod.BANCOLOMBIA_QR: BancolombiaQRBackend,
}


def get_backend(method: PaymentMethod) -> PaymentBackend:
    """Instantiate the appropriate payment backend."""
    backend_cls = BACKEND_REGISTRY.get(method)
    if not backend_cls:
        raise ValueError(f"No backend registered for {method}")
    return backend_cls()


class PaymentService:
    """High-level payment service for Coffee Pie."""

    def __init__(self):
        self._backends: Dict[PaymentMethod, PaymentBackend] = {}

    def _get_backend(self, method: PaymentMethod) -> PaymentBackend:
        if method not in self._backends:
            self._backends[method] = get_backend(method)
        return self._backends[method]

    def create_payment(
        self,
        amount_cop: int,
        method: PaymentMethod = PaymentMethod.PSE,
        customer_email: str = "",
        customer_name: str = "",
        customer_doc: str = "",
        customer_phone: str = "",
        description: str = "",
        metadata: dict = None,
    ) -> PaymentResult:
        """Create a payment and return the result with redirect/QR/BreB key."""
        amount_cr = cop_to_credits(amount_cop)
        request = PaymentRequest(
            amount_cop=amount_cop,
            amount_cr=amount_cr,
            method=method,
            customer_email=customer_email,
            customer_name=customer_name,
            customer_doc=customer_doc,
            customer_phone=customer_phone,
            description=description or f"Recarga Coffee Pie — {amount_cr} Cr",
            metadata=metadata or {},
        )

        backend = self._get_backend(method)
        logger.info(f"Creating payment: {request.reference} — {amount_cop} COP via {method.value}")
        return backend.create_payment(request)

    def check_status(self, transaction_id: str,
                     method: PaymentMethod = PaymentMethod.PSE) -> PaymentResult:
        """Check the status of a payment."""
        backend = self._get_backend(method)
        return backend.check_status(transaction_id)

    def handle_webhook(self, method: PaymentMethod,
                       payload: dict) -> PaymentResult:
        """Process incoming payment webhook."""
        backend = self._get_backend(method)
        result = backend.handle_webhook(payload)

        if result.success:
            logger.info(f"Payment confirmed: {result.transaction_id} — {result.amount_cr} Cr")
        else:
            logger.warning(f"Webhook failed: {result.error_message}")

        return result

    def generate_invoice(
        self,
        customer_doc: str,
        customer_name: str,
        customer_email: str,
        credits_purchased: int,
        payment_method: PaymentMethod,
        amount_cop: int = 0,
    ) -> Invoice:
        """Generate a Colombian electronic invoice (Factura Electrónica)."""
        if amount_cop == 0:
            amount_cop = credits_purchased  # 1 Cr ≈ 1 COP

        iva = calculate_iva(amount_cop)
        total = amount_cop + iva

        import uuid
        invoice = Invoice(
            invoice_number=f"FECP-{uuid.uuid4().hex[:8].upper()}",
            customer_doc=customer_doc,
            customer_name=customer_name,
            customer_email=customer_email,
            items=[{
                "description": f"Creditos Coffee Pie — {credits_purchased} Cr",
                "quantity": 1,
                "unit_price_cop": amount_cop,
                "total_cop": amount_cop,
            }],
            subtotal_cop=amount_cop,
            iva_cop=iva,
            total_cop=total,
            credits_purchased=credits_purchased,
            payment_method=payment_method,
            payment_status=PaymentStatus.PENDING,
        )
        invoice.cufe = generate_cufe(invoice)
        return invoice


# Convenience functions
def create_payment(amount_cop: int, method: str = "pse", **kwargs) -> PaymentResult:
    """Create a payment. method: 'pse', 'breb', 'bancolombia_qr'."""
    payment_method = PaymentMethod(method)
    svc = PaymentService()
    return svc.create_payment(amount_cop=amount_cop, method=payment_method, **kwargs)


def check_payment_status(transaction_id: str, method: str = "pse") -> PaymentResult:
    """Check payment status."""
    payment_method = PaymentMethod(method)
    svc = PaymentService()
    return svc.check_status(transaction_id, payment_method)


def handle_webhook(method: str, payload: dict) -> PaymentResult:
    """Handle incoming webhook."""
    payment_method = PaymentMethod(method)
    svc = PaymentService()
    return svc.handle_webhook(payment_method, payload)
