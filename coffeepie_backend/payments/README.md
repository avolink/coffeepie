# Coffee Pie — Payment Integration Guide

Colombia-specific payment methods for the Coffee Pie QFDM ecosystem.

## Architecture

```
User Browser / App
       │
       ├── PSE: redirect → bank portal → authorize debit → return
       ├── Bre-B: open bank app → send to Coffee Pie key → instant confirmation
       └── Bancolombia QR: scan QR in app → confirm → instant confirmation
              │
              ▼
     Coffee Pie Backend (FastAPI)
       ├── /payments/webhook/pse          ← PSE confirmation (up to 24h)
       ├── /payments/webhook/breb         ← Bre-B notification (< 30s)
       └── /payments/webhook/bancolombia  ← QR confirmation (< 5s)
              │
              ▼
     PaymentService → credit user account → generate invoice
```

## Supported Methods

| Method | Speed | Fee | User Experience |
|--------|-------|-----|-----------------|
| **PSE** | 1–24 hours | ~1.5% + COP 1,000 | Bank redirect, login, authorize |
| **Bre-B** | < 30 seconds | ~0.5% | Open bank app, send to key |
| **Bancolombia QR** | < 5 seconds | ~0.8% | Scan QR, confirm in app |

## Quick Start

```python
from coffeepie_backend.payments import PaymentService, PaymentMethod

svc = PaymentService()

# PSE Payment (ACH debit)
result = svc.create_payment(
    amount_cop=50000,
    method=PaymentMethod.PSE,
    customer_email="usuario@email.com",
    customer_name="Juan Perez",
    customer_doc="1234567890",
)
# → result.redirect_url = "https://pse-test.coffeepie.co/select-bank?..."

# Bre-B Payment (instant transfer)
result = svc.create_payment(
    amount_cop=100000,
    method=PaymentMethod.BREB,
    customer_email="usuario@email.com",
)
# → result.breb_key = "coffeepie@bancolombia"
# User sends money to this key from their bank app.

# Bancolombia QR Payment
result = svc.create_payment(
    amount_cop=75000,
    method=PaymentMethod.BANCOLOMBIA_QR,
)
# → result.qr_code.qr_data = "{...EMVCo payload...}"
# Render this as QR code for the user to scan.

# Check payment status
status = svc.check_status(transaction_id, method=PaymentMethod.BREB)
# → status.status = COMPLETED | PENDING | FAILED
```

## Environment Variables

```bash
# PSE
PSE_API_URL=https://api.pse.com.co/v1
PSE_MERCHANT_ID=your_merchant_id
PSE_API_KEY=your_api_key
PSE_TEST_MODE=true

# Bre-B
BREB_API_URL=https://api.bancolombia.com/breb/v1
BREB_API_KEY=your_api_key
BREB_API_SECRET=your_api_secret
BREB_RECEIVER_KEY=coffeepie@bancolombia
BREB_BANK_CODE=001

# Bancolombia QR
BANCOLOMBIA_QR_API_URL=https://api.bancolombia.com/pagos-qr/v1
BANCOLOMBIA_MERCHANT_ID=COFFEEPIE
BANCOLOMBIA_TERMINAL_ID=WEB001
BANCOLOMBIA_API_KEY=your_api_key
BANCOLOMBIA_API_SECRET=your_api_secret
```

## Testing

```bash
# Rust CLI test tool
coffeepie-payment-test simulate --method breb --amount 100000
coffeepie-payment-test flow --method pse --amount 50000
coffeepie-payment-test webhook-test --provider breb --tx-id TEST-001
coffeepie-payment-test invoice --customer "Juan Perez" --credits 500
coffeepie-payment-test qr-preview --amount 50000

# Python unit test
python -m pytest coffeepie_backend/payments/tests/
```

## Invoice Generation

Invoices follow Colombian DIAN Factura Electrónica spec:

```python
invoice = svc.generate_invoice(
    customer_doc="1234567890",
    customer_name="Juan Perez",
    customer_email="juan@email.com",
    credits_purchased=500,
    payment_method=PaymentMethod.PSE,
)
# → invoice.cufe = "A1B2C3D4..." (SHA-256 hash for DIAN)
# → invoice.total_cop = 59500 (50000 + 19% IVA)
```

## Production Checklist

- [ ] PSE merchant account approved (contact ACH Colombia)
- [ ] Bre-B key registered with your bank
- [ ] Bancolombia QR merchant ID issued
- [ ] DIAN Factura Electrónica authorization
- [ ] SSL certificate for webhook endpoint
- [ ] Webhook IP whitelist configured
- [ ] Payment reconciliation job scheduled (cron every 5 min)
- [ ] Refund flow tested end-to-end
- [ ] Load test: 100 concurrent payments
- [ ] Monitoring: webhook endpoint health checks via `coffeepie-healthd`

## References

- PSE: https://www.pse.com.co
- Bre-B: https://www.banrep.gov.co/es/bre-b
- Bancolombia QR: https://www.bancolombia.com/empresas/pagos/qr
- DIAN Factura Electrónica: https://www.dian.gov.co/factura-electronica
