"""Coffee Pie Payment Webhook Receiver.

FastAPI router that receives payment confirmations from:
  - PSE (ACH debit confirmation, up to 24h after payment)
  - Bre-B (instant transfer notification, < 30s)
  - Bancolombia QR (app payment confirmation, < 5s)

Endpoint: POST /payments/webhook/{provider}
Provider: pse | breb | bancolombia
"""

from fastapi import APIRouter, Request, HTTPException
from .services import handle_webhook as process_webhook
from .models import PaymentMethod
import logging

logger = logging.getLogger("coffeepie.payments.webhook")

router = APIRouter(prefix="/payments/webhook", tags=["payments"])


@router.post("/pse")
async def pse_webhook(request: Request):
    """Receive PSE payment confirmation from ACH."""
    payload = await request.json()
    result = process_webhook("pse", payload)

    if result.success:
        logger.info(f"PSE payment confirmed: {result.transaction_id} — {result.amount_cr} Cr")
        return {"status": "ok", "transaction_id": result.transaction_id}
    else:
        logger.warning(f"PSE webhook rejected: {result.error_message}")
        raise HTTPException(status_code=400, detail=result.error_message)


@router.post("/breb")
async def breb_webhook(request: Request):
    """Receive Bre-B instant transfer confirmation."""
    payload = await request.json()
    result = process_webhook("breb", payload)

    if result.success:
        logger.info(f"Bre-B payment confirmed: {result.transaction_id} — {result.amount_cr} Cr")
        return {"status": "ok", "transaction_id": result.transaction_id}
    else:
        logger.warning(f"Bre-B webhook rejected: {result.error_message}")
        raise HTTPException(status_code=400, detail=result.error_message)


@router.post("/bancolombia")
async def bancolombia_webhook(request: Request):
    """Receive Bancolombia QR payment confirmation."""
    payload = await request.json()
    result = process_webhook("bancolombia_qr", payload)

    if result.success:
        logger.info(f"Bancolombia QR payment confirmed: {result.transaction_id} — {result.amount_cr} Cr")
        return {"status": "ok", "transaction_id": result.transaction_id}
    else:
        logger.warning(f"Bancolombia QR webhook rejected: {result.error_message}")
        raise HTTPException(status_code=400, detail=result.error_message)


@router.get("/health")
async def webhook_health():
    """Health check for webhook receiver."""
    return {
        "status": "ok",
        "providers": ["pse", "breb", "bancolombia"],
        "version": "1.0.0",
    }
