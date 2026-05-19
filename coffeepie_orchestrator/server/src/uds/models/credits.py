# -*- coding: utf-8 -*-

#
# Copyright (c) 2024-2025 Coffee Pie S.A.S. BIC
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Coffee Pie S.A.S. BIC nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Coffee Pie Credit/Billing System models.

Four package tiers:
  FREE:    $0 COP,    0 credits, 1h validity, ads on-demand
  SMALL:   $10,000 COP  -> 10,000 credits, 7 days
  MEDIUM:  $50,000 COP  -> 500,000 credits, 30 days
  LARGE:   $300,000 COP -> 6,000,000 credits, 12 months

Ad credits flow: Advertiser bids -> deducted from Advertiser -> transferred to User
"""
import logging
import typing
import datetime

from django.db import models, transaction
from django.utils.timezone import now as tz_now
from django.db.models.signals import post_save
from django.dispatch import receiver

from .uuid_model import UUIDModel
from ..core.util.model import sql_now

if typing.TYPE_CHECKING:
    from uds.models import User

logger = logging.getLogger(__name__)


class CreditPackageType(models.TextChoices):
    FREE = 'FREE', 'Free Tier'
    SMALL = 'SMALL', 'Small Package'
    MEDIUM = 'MEDIUM', 'Medium Package'
    LARGE = 'LARGE', 'Large Package'


class TransactionType(models.TextChoices):
    PURCHASE = 'PURCHASE', 'Credit Purchase'
    CONSUMPTION = 'CONSUMPTION', 'Slice Usage Consumption'
    AD_BID = 'AD_BID', 'Advertiser Bid Placed'
    AD_REWARD = 'AD_REWARD', 'Ad Reward to User'
    REFUND = 'REFUND', 'Refund'
    BONUS = 'BONUS', 'Promotional Bonus'
    TRANSFER = 'TRANSFER', 'Manual Transfer'
    EXPIRATION = 'EXPIRATION', 'Credit Expiration'


class CreditPackage(UUIDModel):
    name = models.CharField(max_length=64, unique=True)
    package_type = models.CharField(max_length=16, choices=CreditPackageType.choices, unique=True)
    credits = models.PositiveBigIntegerField()
    price_cop = models.PositiveIntegerField()
    validity_days = models.PositiveIntegerField()
    has_no_ads = models.BooleanField(default=False)
    has_mirror = models.BooleanField(default=False)
    has_snapshots = models.BooleanField(default=False)
    has_ha = models.BooleanField(default=False)
    has_live_migration = models.BooleanField(default=False)
    has_non_certified_access = models.BooleanField(default=False)
    has_account_executive = models.BooleanField(default=False)
    support_level = models.CharField(max_length=64, default='basic')
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(default=sql_now)

    class Meta(UUIDModel.Meta):
        db_table = 'uds_credit_packages'
        app_label = 'uds'
        ordering = ('credits',)

    def __str__(self) -> str:
        return f'{self.get_package_type_display()}: {self.credits:,} credits'


class CreditAccount(UUIDModel):
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='credit_account')
    balance = models.BigIntegerField(default=0)
    lifetime_purchased = models.BigIntegerField(default=0)
    lifetime_consumed = models.BigIntegerField(default=0)
    lifetime_ad_rewards = models.BigIntegerField(default=0)
    last_activity = models.DateTimeField(default=sql_now)
    is_advertiser = models.BooleanField(default=False)
    advertiser_name = models.CharField(max_length=128, blank=True, default='')
    advertiser_segments = models.JSONField(default=list, blank=True)
    created = models.DateTimeField(default=sql_now)
    credited_until = models.DateTimeField(null=True, blank=True)

    class Meta(UUIDModel.Meta):
        db_table = 'uds_credit_accounts'
        app_label = 'uds'

    def __str__(self) -> str:
        return f'CreditAccount for {self.user.pretty_name}: {self.balance:,} credits'

    def has_sufficient(self, amount: int) -> bool:
        return self.balance >= amount

    @transaction.atomic
    def add_credits(self, amount: int, txn_type: TransactionType, description: str = '', reference_id: str = '') -> 'CreditTransaction':
        self.balance += amount
        if txn_type == TransactionType.PURCHASE:
            self.lifetime_purchased += amount
        elif txn_type == TransactionType.AD_REWARD:
            self.lifetime_ad_rewards += amount
        self.last_activity = tz_now()
        self.save(update_fields=['balance', 'lifetime_purchased', 'lifetime_ad_rewards', 'last_activity'])
        return CreditTransaction.objects.create(
            user=self.user, account=self, txn_type=txn_type, amount=amount,
            balance_after=self.balance, description=description, reference_id=reference_id,
        )

    @transaction.atomic
    def deduct_credits(self, amount: int, txn_type: TransactionType, description: str = '', reference_id: str = '') -> 'CreditTransaction':
        if not self.has_sufficient(amount):
            raise InsufficientCreditsError(f'Insufficient credits: need {amount}, have {self.balance}')
        self.balance -= amount
        if txn_type == TransactionType.CONSUMPTION:
            self.lifetime_consumed += amount
        self.last_activity = tz_now()
        self.save(update_fields=['balance', 'lifetime_consumed', 'last_activity'])
        return CreditTransaction.objects.create(
            user=self.user, account=self, txn_type=txn_type, amount=-amount,
            balance_after=self.balance, description=description, reference_id=reference_id,
        )


class CreditTransaction(UUIDModel):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='credit_transactions')
    account = models.ForeignKey(CreditAccount, on_delete=models.CASCADE, related_name='transactions')
    txn_type = models.CharField(max_length=16, choices=TransactionType.choices)
    amount = models.BigIntegerField()
    balance_after = models.BigIntegerField()
    description = models.CharField(max_length=256, blank=True, default='')
    reference_id = models.CharField(max_length=128, blank=True, default='')
    timestamp = models.DateTimeField(default=sql_now, db_index=True)

    class Meta(UUIDModel.Meta):
        db_table = 'uds_credit_transactions'
        app_label = 'uds'
        ordering = ('-timestamp',)

    def __str__(self) -> str:
        return f'{self.get_txn_type_display()}: {self.amount:+} credits @ {self.timestamp}'


class AdvertiserBid(UUIDModel):
    advertiser = models.ForeignKey('User', on_delete=models.CASCADE, related_name='ad_bids')
    bid_amount = models.PositiveIntegerField()
    total_budget = models.PositiveBigIntegerField()
    remaining_budget = models.PositiveBigIntegerField()
    segments = models.JSONField(default=dict)
    ad_url = models.URLField(max_length=512)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(default=sql_now)
    expires_at = models.DateTimeField()
    created = models.DateTimeField(default=sql_now)

    class Meta(UUIDModel.Meta):
        db_table = 'uds_ad_bids'
        app_label = 'uds'
        ordering = ('-bid_amount',)

    def __str__(self) -> str:
        return f'Bid by {self.advertiser.pretty_name}: {self.bid_amount} credits'


class InsufficientCreditsError(Exception):
    pass


class AdvertiserApiKey(UUIDModel):
    advertiser = models.ForeignKey('User', on_delete=models.CASCADE, related_name='ad_api_keys')
    api_key = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128, blank=True, default='')
    is_active = models.BooleanField(default=True)
    allowed_origins = models.JSONField(default=list, blank=True)
    rate_limit_per_minute = models.PositiveIntegerField(default=60)
    created = models.DateTimeField(default=sql_now)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta(UUIDModel.Meta):
        db_table = 'uds_ad_api_keys'
        app_label = 'uds'

    def __str__(self) -> str:
        return f'API Key {self.name} for {self.advertiser.pretty_name}'


class AdCampaign(UUIDModel):
    advertiser = models.ForeignKey('User', on_delete=models.CASCADE, related_name='ad_campaigns')
    campaign_name = models.CharField(max_length=256)
    bid_amount = models.PositiveIntegerField()
    daily_budget = models.PositiveBigIntegerField()
    total_budget = models.PositiveBigIntegerField()
    remaining_budget = models.PositiveBigIntegerField()
    ad_content = models.JSONField(default=dict)
    targeting = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    impressions = models.PositiveBigIntegerField(default=0)
    clicks = models.PositiveBigIntegerField(default=0)
    spent = models.PositiveBigIntegerField(default=0)
    starts_at = models.DateTimeField(default=sql_now)
    expires_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(default=sql_now)

    class Meta(UUIDModel.Meta):
        db_table = 'uds_ad_campaigns'
        app_label = 'uds'
        ordering = ('-bid_amount',)

    def __str__(self) -> str:
        return f'Campaign {self.campaign_name} by {self.advertiser.pretty_name}'


@receiver(post_save, sender='uds.User')
def create_credit_account(sender, instance, created, **kwargs):
    if created:
        CreditAccount.objects.create(user=instance)


DEFAULT_PACKAGES = [
    {'name': 'Capa Gratuita', 'package_type': CreditPackageType.FREE, 'credits': 0, 'price_cop': 0, 'validity_days': 0},
    {'name': 'Paquete Pequeño', 'package_type': CreditPackageType.SMALL, 'credits': 10000, 'price_cop': 10000, 'validity_days': 7, 'has_no_ads': True},
    {'name': 'Paquete Mediano', 'package_type': CreditPackageType.MEDIUM, 'credits': 500000, 'price_cop': 50000, 'validity_days': 30, 'has_no_ads': True, 'has_mirror': True, 'has_snapshots': True},
    {'name': 'Paquete Grande', 'package_type': CreditPackageType.LARGE, 'credits': 6000000, 'price_cop': 300000, 'validity_days': 365, 'has_no_ads': True, 'has_mirror': True, 'has_snapshots': True, 'has_ha': True, 'has_live_migration': True, 'has_non_certified_access': True, 'has_account_executive': True},
]


def seed_default_packages():
    for pkg in DEFAULT_PACKAGES:
        CreditPackage.objects.get_or_create(package_type=pkg['package_type'], defaults=pkg)
