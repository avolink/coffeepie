"""Abstract payment backend interface."""

from abc import ABC, abstractmethod
from typing import Optional
from ..models import PaymentRequest, PaymentResult, PaymentMethod


class PaymentBackend(ABC):
    """Base class for all payment backends.

    Each backend implements the specific protocol for a Colombian payment method:
      - BreBBackend: Bre-B instant transfers
      - PSEBackend: Pagos Seguros en Línea (ACH debit)
      - BancolombiaQRBackend: QR code scan-to-pay
    """

    @property
    @abstractmethod
    def method(self) -> PaymentMethod:
        """The payment method this backend handles."""
        ...

    @abstractmethod
    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        """Initiate a payment. Returns result with redirect URL, QR code, or BreB key."""
        ...

    @abstractmethod
    def check_status(self, transaction_id: str) -> PaymentResult:
        """Poll the payment status. Used for async methods like PSE and Bre-B."""
        ...

    def handle_webhook(self, payload: dict) -> PaymentResult:
        """Process an incoming webhook notification from the payment provider."""
        raise NotImplementedError(f"Webhook not implemented for {self.method}")

    def refund(self, transaction_id: str, amount_cop: Optional[int] = None) -> PaymentResult:
        """Refund a completed payment."""
        raise NotImplementedError(f"Refunds not supported for {self.method}")

    @staticmethod
    def generate_reference(prefix: str = "CP") -> str:
        """Generate a unique payment reference."""
        import uuid
        return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"
