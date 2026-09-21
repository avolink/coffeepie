"""COFP metering — the core accounting rule of the Coffee Pie economy.

    1 COFP = 1 Slice · minute, *effectively served*.

A "slice" is the base unit of capacity defined by the DC Agent
(see coffeepie_orchestrator/dc-agent/src/types.rs::SliceSpec). An instance that
occupies N slices and streams to a connected client for M minutes mints N·M COFP
for the Provider that hosted it.

The load-bearing word is **effectively served**. A VM that is merely powered on,
booting, or idle with no client attached delivers no value and therefore mints
nothing. Metering keys off whether the platform actually delivered a stream, not
off VM uptime. This protects both sides: Providers are paid only for value
delivered, and Advertisers/consumers are billed only for sessions they actually
received.

All amounts are Decimal (never float) so the ledger is exact and auditable.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

# 1 COFP per slice·minute. Lives here so the constant has exactly one home.
COFP_PER_SLICE_MINUTE = Decimal(1)
SECONDS_PER_MINUTE = Decimal(60)

# COFP is metered to the micro (1e-6). Per-second sampling produces fractional
# COFP, so we quantize every conversion to keep the ledger free of float drift.
COFP_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class UsageSample:
    """One metering window for one running instance.

    Emitted by the streaming layer (Sunshine session lifecycle) and forwarded
    through the DC Agent. `streaming` must be True ONLY while a client was paired
    and actually receiving frames during this window — that is the definition of
    "effectively served". See README "What I need from the backend partner".
    """

    instance_id: str
    provider_id: str  # who hosted it → who gets paid
    user_id: str      # who consumed it → who gets billed
    slices: int       # base slices this instance occupies (SliceSpec factor)
    seconds: int      # wall-clock seconds covered by this sample
    streaming: bool   # True iff a client was connected and receiving frames

    def effective_slice_seconds(self) -> int:
        """Slice·seconds that count toward COFP. Zero unless actually served."""
        if not self.streaming or self.slices <= 0 or self.seconds <= 0:
            return 0
        return self.slices * self.seconds


def slice_seconds_to_cofp(slice_seconds: int) -> Decimal:
    """Convert effective slice·seconds into COFP, quantized to the micro."""
    if slice_seconds <= 0:
        return Decimal(0)
    raw = Decimal(slice_seconds) / SECONDS_PER_MINUTE * COFP_PER_SLICE_MINUTE
    return raw.quantize(COFP_QUANTUM, rounding=ROUND_HALF_UP)


def cofp_for_sample(sample: UsageSample) -> Decimal:
    """COFP minted by a single usage sample (0 if not effectively served)."""
    return slice_seconds_to_cofp(sample.effective_slice_seconds())
