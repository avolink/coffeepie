"""Coffee Pie Payments Module.

Colombia-specific payment integration for the Coffee Pie ecosystem.

Supports:
  - PSE (Pagos Seguros en Línea) — ACH debit, redirect-based
  - Bre-B — Instant inter-bank transfers 24/7
  - Bancolombia QR — Scan-to-pay with Colombia's largest banking app
  - Future: Stripe, PayPal, COFP token burn

Usage:
    from coffeepie_backend.payments import PaymentService, PaymentMethod

    svc = PaymentService()
    result = svc.create_payment(
        amount_cop=50000,
        method=PaymentMethod.PSE,
        customer_email="usuario@email.com",
        customer_name="Juan Perez",
        customer_doc="1234567890",
    )
    print(result.redirect_url)  # Send user to their bank
"""

from .models import (
    PaymentRequest, PaymentResult, PaymentStatus, PaymentMethod,
    Invoice, BreBPaymentKey, BreBTransfer, BancolombiaQR,
    cop_to_credits, credits_to_cop, calculate_iva, generate_cufe,
    cofp_to_cop, cofp_to_credits,
)
from .services import PaymentService, create_payment, check_payment_status
from .webhook import router as webhook_router

__all__ = [
    "PaymentRequest", "PaymentResult", "PaymentStatus", "PaymentMethod",
    "Invoice", "BreBPaymentKey", "BreBTransfer", "BancolombiaQR",
    "PaymentService", "create_payment", "check_payment_status",
    "webhook_router",
    "cop_to_credits", "credits_to_cop", "calculate_iva", "generate_cufe",
    "cofp_to_cop", "cofp_to_credits",
]
