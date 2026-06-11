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
Coffee Pie Credit/Billing REST API.

Routes (under /coffeepie/credits/):
  GET  balance          -> Current user credit balance
  GET  packages         -> Available credit packages
  POST purchase         -> Purchase a credit package
  GET  transactions     -> Transaction history
  POST consume          -> Consume credits for slice usage
  POST ad/bid           -> Advertiser places a bid
  GET  ad/bids          -> List active advertiser bids
  POST ad/reward        -> Ad won: transfer credits from advertiser to user
  POST ad/register      -> Register current user as advertiser
"""
import datetime
import logging
import typing

from django.utils import timezone
from django.db import transaction as db_transaction
from django.core.exceptions import ObjectDoesNotExist

from uds.core import consts, exceptions
from uds.REST import Handler

logger = logging.getLogger(__name__)

COFFEE_PIE_SLICE_COST_PER_HOUR = 1


class Credits(Handler):
    PATH = 'coffeepie'

    def _account(self):
        from uds.models import CreditAccount
        return CreditAccount.objects.get(user=self._user)

    def _json_balance(self, account):
        return {
            'balance': account.balance,
            'lifetime_purchased': account.lifetime_purchased,
            'lifetime_consumed': account.lifetime_consumed,
            'lifetime_ad_rewards': account.lifetime_ad_rewards,
            'is_advertiser': account.is_advertiser,
            'user_name': self._user.pretty_name,
        }

    def _json_package(self, pkg):
        features = []
        if pkg.has_no_ads:
            features.append('sin_interrupciones')
        if pkg.has_mirror:
            features.append('replicacion_espejo')
        if pkg.has_snapshots:
            features.append('respaldos_nube')
        if pkg.has_ha:
            features.append('alta_disponibilidad')
        if pkg.has_live_migration:
            features.append('migracion_vivo')
        if pkg.has_non_certified_access:
            features.append('acceso_no_certificados')
        if pkg.has_account_executive:
            features.append('ejecutivo_cuenta')
        return {
            'id': pkg.uuid,
            'name': pkg.name,
            'package_type': pkg.package_type,
            'credits': pkg.credits,
            'price_cop': pkg.price_cop,
            'validity_days': pkg.validity_days,
            'features': features,
        }

    def get(self) -> typing.Any:
        args = self._args
        if not args:
            raise exceptions.rest.RequestError('Missing operation')

        operation = args[0].lower()

        if operation == 'balance':
            return self._json_balance(self._account())

        if operation == 'packages':
            from uds.models import CreditPackage
            return [self._json_package(p) for p in CreditPackage.objects.filter(is_active=True).order_by('credits')]

        if operation == 'transactions':
            from uds.models import CreditTransaction
            limit = int(self._params.get('limit', 50))
            offset = int(self._params.get('offset', 0))
            txn_qs = CreditTransaction.objects.filter(user=self._user).order_by('-timestamp')[offset:offset + limit]
            return [{
                'id': t.uuid, 'txn_type': t.txn_type, 'amount': t.amount,
                'balance_after': t.balance_after, 'description': t.description,
                'timestamp': t.timestamp.isoformat(),
            } for t in txn_qs]

        if operation == 'ad' and len(args) >= 2:
            sub_op = args[1].lower()
            if sub_op == 'bids':
                from uds.models import AdvertiserBid
                now = timezone.localtime()
                bids = AdvertiserBid.objects.filter(is_active=True, expires_at__gt=now, remaining_budget__gt=0).order_by('-bid_amount')
                return [{
                    'id': b.uuid, 'advertiser_name': b.advertiser.real_name or b.advertiser.name,
                    'bid_amount': b.bid_amount, 'total_budget': b.total_budget,
                    'remaining_budget': b.remaining_budget, 'segments': b.segments,
                    'is_active': b.is_active, 'expires_at': b.expires_at.isoformat(),
                } for b in bids]

            if sub_op == 'winning':
                from uds.models import AdvertiserBid
                now = timezone.localtime()
                winning_bid = AdvertiserBid.objects.filter(is_active=True, expires_at__gt=now, remaining_budget__gt=0).order_by('-bid_amount').first()
                if winning_bid:
                    return {
                        'id': winning_bid.uuid, 'advertiser_name': winning_bid.advertiser.real_name or winning_bid.advertiser.name,
                        'bid_amount': winning_bid.bid_amount, 'ad_url': winning_bid.ad_url,
                    }
                return {'id': None, 'message': 'No active bids'}

        raise exceptions.rest.RequestError(f'Unknown operation: {"/".join(args)}')

    def post(self) -> typing.Any:
        args = self._args
        if not args:
            raise exceptions.rest.RequestError('Missing operation')

        operation = args[0].lower()

        if operation == 'purchase':
            return self._purchase()

        if operation == 'consume':
            return self._consume()

        if operation == 'ad' and len(args) >= 2:
            sub_op = args[1].lower()
            if sub_op == 'bid':
                return self._ad_bid()
            if sub_op == 'reward':
                return self._ad_reward()
            if sub_op == 'register':
                return self._ad_register()

        if operation == 'payment' and len(args) >= 2:
            return self._payment_notify()

        raise exceptions.rest.RequestError(f'Unknown operation: {"/".join(args)}')

    def _purchase(self):
        from uds.models import CreditPackage, CreditAccount, TransactionType
        pkg_uuid = self._params.get('package_id')
        if not pkg_uuid:
            raise exceptions.rest.RequestError('package_id is required')
        try:
            pkg = CreditPackage.objects.get(uuid=pkg_uuid, is_active=True)
        except CreditPackage.DoesNotExist:
            raise exceptions.rest.RequestError('Invalid or inactive package')
        with db_transaction.atomic():
            account = CreditAccount.objects.select_for_update().get(user=self._user)
            txn = account.add_credits(
                amount=pkg.credits,
                txn_type=TransactionType.PURCHASE,
                description=f'Purchase: {pkg.name} - {pkg.credits:,} credits',
                reference_id=pkg_uuid,
            )
            if pkg.validity_days > 0:
                account.credited_until = timezone.localtime() + datetime.timedelta(days=pkg.validity_days)
                account.save(update_fields=['credited_until'])
        return {
            'transaction_id': txn.uuid,
            'credits_added': pkg.credits,
            'balance': account.balance,
            'price_cop': pkg.price_cop,
            'valid_until': account.credited_until.isoformat() if account.credited_until else None,
        }

    def _consume(self):
        from uds.models import CreditAccount, TransactionType, InsufficientCreditsError
        slice_count = int(self._params.get('slice_count', 1))
        hours = int(self._params.get('hours', 1))
        cost = slice_count * COFFEE_PIE_SLICE_COST_PER_HOUR * hours
        with db_transaction.atomic():
            account = CreditAccount.objects.select_for_update().get(user=self._user)
            if account.balance == 0:
                return {'status': 'free_tier', 'cost': 0, 'balance': 0, 'ads_required': True}
            try:
                txn = account.deduct_credits(
                    amount=cost, txn_type=TransactionType.CONSUMPTION,
                    description=f'Slice usage: {slice_count} slices x {hours}h = {cost} credits',
                )
                return {'status': 'ok', 'cost': cost, 'balance': account.balance, 'transaction_id': txn.uuid}
            except InsufficientCreditsError:
                remaining = account.balance
                if remaining > 0:
                    account.deduct_credits(
                        amount=remaining, txn_type=TransactionType.CONSUMPTION,
                        description=f'Slice usage (partial): used {remaining} of {cost} credits',
                    )
                return {'status': 'insufficient', 'cost': remaining, 'balance': 0, 'needed': cost - remaining}

    def _ad_register(self):
        from uds.models import CreditAccount
        segments = self._params.get('segments', [])
        name = self._params.get('advertiser_name', '')
        with db_transaction.atomic():
            account = CreditAccount.objects.get(user=self._user)
            account.is_advertiser = True
            account.advertiser_name = name or self._user.pretty_name
            account.advertiser_segments = segments
            account.save(update_fields=['is_advertiser', 'advertiser_name', 'advertiser_segments'])
        return {'status': 'ok', 'is_advertiser': True, 'advertiser_name': account.advertiser_name}

    def _ad_bid(self):
        from uds.models import CreditAccount, TransactionType, AdvertiserBid
        account = CreditAccount.objects.get(user=self._user)
        if not account.is_advertiser:
            raise exceptions.rest.RequestError('Not registered as advertiser')
        bid_amount = int(self._params.get('bid_amount', 0))
        total_budget = int(self._params.get('total_budget', 0))
        segments = self._params.get('segments', {})
        ad_url = self._params.get('ad_url', '')
        expires_at_str = self._params.get('expires_at', '')
        if bid_amount <= 0 or total_budget <= 0:
            raise exceptions.rest.RequestError('bid_amount and total_budget must be positive')
        if total_budget < bid_amount:
            raise exceptions.rest.RequestError('total_budget must be >= bid_amount')
        if not ad_url:
            raise exceptions.rest.RequestError('ad_url is required')
        try:
            expires_at = datetime.datetime.fromisoformat(expires_at_str)
        except (ValueError, TypeError):
            raise exceptions.rest.RequestError('expires_at must be ISO datetime')
        with db_transaction.atomic():
            account = CreditAccount.objects.select_for_update().get(user=self._user)
            if not account.has_sufficient(total_budget):
                raise exceptions.rest.RequestError(f'Need {total_budget} credits, have {account.balance}')
            account.deduct_credits(
                amount=total_budget, txn_type=TransactionType.AD_BID,
                description=f'Ad bid: {bid_amount} credits/impression, budget {total_budget}',
            )
            bid = AdvertiserBid.objects.create(
                advertiser=self._user, bid_amount=bid_amount, total_budget=total_budget,
                remaining_budget=total_budget, segments=segments, ad_url=ad_url,
                starts_at=timezone.localtime(), expires_at=expires_at,
            )
        return {
            'bid_id': bid.uuid, 'bid_amount': bid_amount, 'total_budget': total_budget,
            'remaining_budget': bid.remaining_budget, 'balance_after': account.balance,
        }

    def _ad_reward(self):
        from uds.models import AdvertiserBid, CreditAccount, TransactionType
        bid_id = self._params.get('bid_id')
        if not bid_id:
            raise exceptions.rest.RequestError('bid_id is required')
        with db_transaction.atomic():
            try:
                bid = AdvertiserBid.objects.select_for_update().get(uuid=bid_id, is_active=True)
            except AdvertiserBid.DoesNotExist:
                raise exceptions.rest.NotFound('Bid not found')
            reward = min(bid.bid_amount, bid.remaining_budget)
            bid.remaining_budget -= reward
            if bid.remaining_budget <= 0:
                bid.is_active = False
            bid.save()
            user_account = CreditAccount.objects.select_for_update().get(user=self._user)
            txn = user_account.add_credits(
                amount=reward, txn_type=TransactionType.AD_REWARD,
                description=f'Ad reward from {bid.advertiser.pretty_name}: {reward} credits',
                reference_id=bid_id,
            )
        return {'status': 'ok', 'credits_rewarded': reward, 'balance': user_account.balance, 'ad_url': bid.ad_url}

    def _payment_notify(self):
        from uds.models import CreditPackage, CreditAccount, TransactionType
        action = self._args[1].lower()
        if action == 'verify':
            pkg_type = self._params.get('package_type', 'SMALL')
            try:
                pkg = CreditPackage.objects.get(package_type=pkg_type, is_active=True)
            except CreditPackage.DoesNotExist:
                raise exceptions.rest.NotFound('Package not found')
            return {
                'bank': 'Bancolombia',
                'account_type': 'Cuenta Corriente',
                'account_name': 'Coffee Pie S.A.S. BIC',
                'nit': '901.xxx.xxx-x',
                'reference_prefix': 'CP',
                'package': pkg_type,
                'amount_cop': pkg.price_cop,
                'credits': pkg.credits,
            }
        if action == 'confirm':
            pkg_type = self._params.get('package_type', 'SMALL')
            reference = self._params.get('reference', '')
            try:
                pkg = CreditPackage.objects.get(package_type=pkg_type, is_active=True)
            except CreditPackage.DoesNotExist:
                raise exceptions.rest.NotFound('Package not found')
            with db_transaction.atomic():
                account = CreditAccount.objects.select_for_update().get(user=self._user)
                txn = account.add_credits(
                    amount=pkg.credits,
                    txn_type=TransactionType.PURCHASE,
                    description=f'Bank transfer: {pkg.name} - ref {reference}',
                    reference_id=reference,
                )
                if pkg.validity_days > 0:
                    account.credited_until = timezone.localtime() + datetime.timedelta(days=pkg.validity_days)
                    account.save(update_fields=['credited_until'])
            return {'status': 'ok', 'credits': pkg.credits, 'balance': account.balance}
        raise exceptions.rest.RequestError('Unknown payment action')
