"""Coffee Pie Payment Models.

Colombia-specific payment methods for the QFDM ecosystem:
  - Bre-B: Instant inter-bank transfers (Banco de la República)
  - PSE: Pagos Seguros en Línea (ACH debit, redirect-based)
  - Bancolombia QR: QR code scan-to-pay

All amounts in COP (Colombian Pesos). Conversion rates:
  Consumer: 20 Cr = 1 COP (6'000'000 Cr = 300'000 COP)
  Contributor burn: 1 COFP = 10 Cr
  Provider base: 1 COFP = 0.29 COP (global base cost, governance-voted)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime
import hashlib
import uuid


class PaymentMethod(str, Enum):
    BREB = "breb"               # Bre-B instant transfer
    PSE = "pse"                 # PSE ACH debit
    BANCOLOMBIA_QR = "bancolombia_qr"
    BANCOLOMBIA_APP = "bancolombia_app"
    CARD_CREDIT = "card_credit"
    CARD_DEBIT = "card_debit"
    CRYPTO_COFP = "cofp"        # COFP token burn


class PaymentStatus(str, Enum):
    PENDING = "pending"           # Created, awaiting payment
    PROCESSING = "processing"     # Payment detected, confirming
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class Currency(str, Enum):
    COP = "COP"
    USD = "USD"
    CR = "Cr"     # Coffee Pie Credits


@dataclass
class PaymentRequest:
    """A payment to be processed."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    amount_cop: int = 0                    # Amount in COP (no decimals)
    amount_cr: int = 0                     # Equivalent in Credits
    method: PaymentMethod = PaymentMethod.PSE
    currency: Currency = Currency.COP
    description: str = ""
    customer_email: str = ""
    customer_name: str = ""
    customer_doc: str = ""                 # CC/NIT (Colombian ID)
    customer_phone: str = ""
    breb_key: str = ""                     # Bre-B payment key
    reference: str = ""                    # External payment reference
    return_url: str = "https://coffeepie.co/pago-exitoso"
    cancel_url: str = "https://coffeepie.co/tienda"
    webhook_url: str = "https://api.coffeepie.co/payments/webhook"
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: str = ""                   # ISO timestamp, auto-set if empty

    def __post_init__(self):
        if not self.reference:
            self.reference = f"CP-{self.id[:8].upper()}"
        if not self.expires_at:
            # Payments expire in 30 minutes
            from datetime import timedelta
            dt = datetime.utcnow() + timedelta(minutes=30)
            self.expires_at = dt.isoformat()


@dataclass
class BreBPaymentKey:
    """Bre-B key types per Banco de la República spec."""
    key_type: str         # phone, email, doc, random
    key_value: str        # The actual key (phone number, email, etc.)
    bank_code: str        # Colombian bank code (e.g., "001" for Bancolombia)
    account_type: str     # savings, checking
    account_number: str   # Account number receiving the payment


@dataclass
class BreBTransfer:
    """A Bre-B instant transfer response."""
    transaction_id: str
    sender_key: str
    receiver_key: str
    amount_cop: int
    status: PaymentStatus
    timestamp: str
    bank_response_code: str = ""


@dataclass
class BancolombiaQR:
    """Bancolombia QR code payment data."""
    qr_data: str                         # Raw QR payload (text encoded in QR)
    qr_image_base64: str = ""            # Optional pre-rendered QR PNG base64
    merchant_id: str = ""
    terminal_id: str = ""
    amount_cop: int = 0
    reference: str = ""
    expires_at: str = ""


@dataclass
class PaymentResult:
    """Result of a payment attempt."""
    success: bool
    transaction_id: str = ""
    status: PaymentStatus = PaymentStatus.PENDING
    method: PaymentMethod = PaymentMethod.PSE
    amount_cop: int = 0
    amount_cr: int = 0
    gateway_response: str = ""
    redirect_url: str = ""               # For PSE: bank redirect URL
    qr_code: Optional[BancolombiaQR] = None
    breb_key: str = ""                   # Bre-B key for customer to send to
    error_message: str = ""
    paid_at: str = ""


@dataclass
class Invoice:
    """Coffee Pie invoice (Factura Electrónica Colombia compatible)."""
    invoice_number: str
    customer_doc: str
    customer_name: str
    customer_email: str
    items: list = field(default_factory=list)
    subtotal_cop: int = 0
    iva_cop: int = 0                     # 19% IVA Colombia
    total_cop: int = 0
    credits_purchased: int = 0
    payment_method: PaymentMethod = PaymentMethod.PSE
    payment_status: PaymentStatus = PaymentStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    paid_at: str = ""
    cufe: str = ""                       # CUFE for DIAN electronic invoice
    qr_dian: str = ""                    # DIAN QR code data


def generate_cufe(invoice: Invoice) -> str:
    """Generate CUFE (Código Único de Factura Electrónica) for DIAN compliance."""
    raw = f"{invoice.invoice_number}|{invoice.customer_doc}|{invoice.total_cop}|{invoice.created_at}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64].upper()


def calculate_iva(subtotal_cop: int) -> int:
    """Colombian IVA: 19%."""
    return int(subtotal_cop * 0.19)


def cop_to_credits(cop: int) -> int:
    """Convert COP to Credits. 1 Cr ≈ 1 COP at parity."""
    return cop  # 1:1 parity for MVP


def credits_to_cop(cr: int) -> int:
    """Convert Credits to COP. 20 Cr = 1 COP (consumer rate: 6M Cr = 300K COP)."""
    return cr // 20


def cofp_to_cop(cofp: int) -> int:
    """Convert COFP to COP. 1 COFP = 0.29 COP (global base cost)."""
    return cofp * 29 // 100


def cofp_to_credits(cofp: int) -> int:
    """Convert COFP to Credits. 1 COFP = 10 Cr (contributor burn rate)."""
    return cofp * 10


# ── Parking Fee (dormant Slices) ──────────────────────────────────────
# A powered-off or suspended Slice (e.g. a stopped Proxmox VM) releases its
# compute/power but still reserves SSD (8 GB) + HDD (125 GB) on a provider's
# node, so it accrues a reduced "Parking Fee". These rates are governance
# parameters (set by the same regional-pricing vote as avgSliceCost), not
# fixed constants — keep them here as the single source of truth. See
# PROVIDERS.md "Dormant Slices — The Parking Fee".
PARKING_FEE_CR_PER_SLICE_HOUR = 10      # consumer charge, in Credits (~10% of active 100 Cr/h)
PARKING_FREE_DORMANT_SLICES = 9         # first N dormant Slices per account are free
PARKING_COFP_MINT_PER_SLICE_HOUR = 1.5  # provider earning (vs 60 COFP/hour active)


def parking_fee_cr(dormant_slices: int, hours: float) -> int:
    """Consumer Parking Fee in Credits for dormant (off/suspended) Slices.

    The first PARKING_FREE_DORMANT_SLICES per account are free; the fee applies
    from the (PARKING_FREE_DORMANT_SLICES + 1)-th dormant Slice and up.
    """
    chargeable = max(0, dormant_slices - PARKING_FREE_DORMANT_SLICES)
    return int(chargeable * PARKING_FEE_CR_PER_SLICE_HOUR * hours)


def dormant_cofp_mint(dormant_slices: int, hours: float) -> float:
    """COFP minted to the provider for hosting dormant Slices.

    Unlike the consumer fee, there is NO free allowance here: the provider
    reserves storage for *every* dormant Slice, so it earns on all of them —
    the platform absorbs the cost of a consumer's first free Slices.
    """
    return dormant_slices * PARKING_COFP_MINT_PER_SLICE_HOUR * hours
