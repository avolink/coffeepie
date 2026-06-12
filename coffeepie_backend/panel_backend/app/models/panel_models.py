"""Pydantic request/response models for the panel API."""

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    """QA-local login request."""
    email: str
    password: str


class LoginOut(BaseModel):
    """QA-local login response. `access_token` is a Supabase-shaped HS256 JWT."""
    access_token: str
    token_type: str = "bearer"
    uid: str
    email: str
    roles: list[str]


class RegisterIn(BaseModel):
    """QA-local registration request."""
    name: str
    email: str
    password: str = Field(min_length=8)


class UsageEventIn(BaseModel):
    """Metering event forwarded from the DC Agent / streaming layer.

    One event = one accounting window for one instance. `streaming` MUST reflect
    whether a client was actually receiving frames during the window (see
    metering.py — "effectively served").
    """
    instance_id: str
    provider_id: str
    user_id: str
    slices: int = Field(ge=0)
    seconds: int = Field(ge=0)
    streaming: bool


class AccrualOut(BaseModel):
    instance_id: str
    cofp_minted: str          # Decimal serialized as string to avoid float loss
    provider_balance: str


class BalanceOut(BaseModel):
    account_id: str
    cofp_balance: str
    voting_power: str


class ProviderSummaryOut(BaseModel):
    account_id: str
    cofp_balance: str
    cofp_this_month: str
    served_instances: int


class WithdrawIn(BaseModel):
    cofp_amount: str = Field(description="COFP to burn, as a decimal string")
    tier: str = Field(default="tier1", pattern=r"^tier[1-5]$")
    concept: str = Field(default="", max_length=200)


class WithdrawOut(BaseModel):
    cofp_burned: str
    tier: str
    effective_rate_cop: str
    payout_cop: int
    ledger_entry_id: str
    note: str
