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
Coffee Pie Ads API/MCP - Public advertiser-facing REST API.
Documented at coffeepie.co/api.html

Routes (under /coffeepie/ads/):
  POST ad/request        -> Advertiser requests ad placement for a user session
  POST campaign/create   -> Create a new ad campaign
  GET  campaign/list     -> List advertiser's campaigns
  GET  campaign/{id}     -> Get campaign details + stats
  POST campaign/pause    -> Pause/resume a campaign
  GET  analytics         -> Campaign performance analytics
  GET  segments          -> Available targeting segments
"""
import datetime
import json
import logging
import typing
import uuid

from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Q

from uds.core import exceptions
from uds.REST import Handler

logger = logging.getLogger(__name__)


def _api_key_auth(params, request=None):
    from uds.models import AdvertiserApiKey, CreditAccount
    api_key = params.get('api_key') or (request and request.META.get('HTTP_X_API_KEY', ''))
    if not api_key:
        return None
    try:
        key = AdvertiserApiKey.objects.select_related('advertiser__credit_account').get(api_key=api_key, is_active=True)
        key.last_used = timezone.localtime()
        key.save(update_fields=['last_used'])
        return key
    except AdvertiserApiKey.DoesNotExist:
        return None


def _match_targeting(campaign_targeting, user_context):
    if not campaign_targeting:
        return True

    demographics = user_context.get('demographics', {})
    interests = user_context.get('interests', [])
    behavior = user_context.get('behavior', {})

    target_demo = campaign_targeting.get('demographics', {})
    if target_demo:
        min_age = target_demo.get('min_age', 0)
        max_age = target_demo.get('max_age', 999)
        user_age_range = demographics.get('age_range', [0, 999])
        user_age = (user_age_range[0] + user_age_range[1]) // 2 if len(user_age_range) == 2 else 25
        if user_age < min_age or user_age > max_age:
            return False

        target_countries = target_demo.get('countries', [])
        if target_countries and demographics.get('location', {}).get('country', '') not in target_countries:
            return False

        target_langs = target_demo.get('languages', [])
        if target_langs:
            user_langs = [l.get('code', '') for l in demographics.get('languages', [])]
            if not any(l in target_langs for l in user_langs):
                return False

    target_interests = campaign_targeting.get('interests', [])
    if target_interests and not any(i in interests for i in target_interests):
        return False

    target_behavior = campaign_targeting.get('behavior', {})
    if target_behavior:
        return True

    return True


class Ads(Handler):
    PATH = 'coffeepie'

    def _auth(self):
        key = _api_key_auth(self._params, self._request if hasattr(self, '_request') else None)
        if not key:
            raise exceptions.rest.AccessDenied('Invalid or missing API key')
        self._advertiser = key.advertiser
        return self._advertiser

    def get(self) -> typing.Any:
        args = self._args
        if not args:
            raise exceptions.rest.RequestError('Missing operation')

        op = args[0].lower()

        if op == 'campaign':
            self._auth()
            if len(args) >= 2 and args[1].lower() == 'list':
                return self._campaign_list()
            if len(args) >= 2:
                return self._campaign_detail(args[1])
        if op == 'analytics':
            self._auth()
            return self._campaign_analytics()
        if op == 'segments':
            return self._available_segments()

        raise exceptions.rest.RequestError(f'Unknown operation: {"/".join(args)}')

    def post(self) -> typing.Any:
        args = self._args
        if not args:
            raise exceptions.rest.RequestError('Missing operation')

        op = args[0].lower()

        if op == 'ad':
            if len(args) >= 2 and args[1].lower() == 'request':
                self._auth()
                return self._ad_request()
        if op == 'campaign':
            self._auth()
            if len(args) >= 2 and args[1].lower() == 'create':
                return self._create_campaign()
            if len(args) >= 3 and args[1].lower() == 'pause':
                return self._pause_campaign(args[2])
        if op == 'key':
            self._auth()
            if len(args) >= 2 and args[1].lower() == 'create':
                return self._create_api_key()

        raise exceptions.rest.RequestError(f'Unknown operation: {"/".join(args)}')

    def _ad_request(self):
        from uds.models import AdCampaign, AdvertiserBid, CreditAccount, TransactionType

        body = self._params
        request_id = body.get('request_id', str(uuid.uuid4()))
        user_context = body.get('user_context', {})

        now = timezone.localtime()
        campaigns = AdCampaign.objects.filter(
            is_active=True, remaining_budget__gt=0,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        ).order_by('-bid_amount')

        best_match = None
        for campaign in campaigns:
            if _match_targeting(campaign.targeting, user_context):
                best_match = campaign
                break

        if not best_match:
            return {
                'request_id': request_id,
                'status': 'no_match',
                'message': 'No active campaigns match this user context.',
                'ads': [],
                'timestamp': now.isoformat(),
            }

        reward = best_match.bid_amount
        if reward > best_match.remaining_budget:
            reward = best_match.remaining_budget

        with db_transaction.atomic():
            campaign = AdCampaign.objects.select_for_update().get(pk=best_match.pk)
            campaign.impressions += 1
            campaign.spent += reward
            campaign.remaining_budget -= reward
            if campaign.remaining_budget <= 0:
                campaign.is_active = False
            campaign.save()

        return {
            'request_id': request_id,
            'status': 'matched',
            'campaign_id': best_match.uuid,
            'campaign_name': best_match.campaign_name,
            'bid_amount': reward,
            'ad_content': best_match.ad_content,
            'ad_url': best_match.ad_content.get('url', ''),
            'timestamp': now.isoformat(),
        }

    def _create_campaign(self):
        from uds.models import CreditAccount, AdCampaign
        advertiser = self._advertiser
        name = self._params.get('campaign_name', '')
        bid_amount = int(self._params.get('bid_amount', 0))
        daily_budget = int(self._params.get('daily_budget', 0))
        total_budget = int(self._params.get('total_budget', 0))
        ad_content = self._params.get('ad_content', {})
        targeting = self._params.get('targeting', {})
        expires_at_str = self._params.get('expires_at', '')

        if not name or bid_amount <= 0 or total_budget <= 0:
            raise exceptions.rest.RequestError('campaign_name, bid_amount, and total_budget are required')
        if total_budget < bid_amount:
            raise exceptions.rest.RequestError('total_budget must be >= bid_amount')

        expires_at = None
        if expires_at_str:
            try:
                expires_at = datetime.datetime.fromisoformat(expires_at_str)
            except (ValueError, TypeError):
                pass

        with db_transaction.atomic():
            account = CreditAccount.objects.select_for_update().get(user=advertiser)
            if not account.has_sufficient(total_budget):
                raise exceptions.rest.RequestError(f'Need {total_budget} credits, have {account.balance}')
            account.deduct_credits(
                amount=total_budget,
                txn_type=TransactionType.AD_BID,
                description=f'Campaign: {name} - bid {bid_amount}, budget {total_budget}',
            )
            campaign = AdCampaign.objects.create(
                advertiser=advertiser, campaign_name=name,
                bid_amount=bid_amount, daily_budget=daily_budget or total_budget,
                total_budget=total_budget, remaining_budget=total_budget,
                ad_content=ad_content, targeting=targeting,
                is_active=True, starts_at=timezone.localtime(),
                expires_at=expires_at,
            )
        return {
            'campaign_id': campaign.uuid,
            'campaign_name': name,
            'bid_amount': bid_amount,
            'total_budget': total_budget,
            'remaining_budget': total_budget,
            'status': 'active',
        }

    def _campaign_list(self):
        from uds.models import AdCampaign
        campaigns = AdCampaign.objects.filter(advertiser=self._advertiser).order_by('-created')
        return [{
            'id': c.uuid, 'name': c.campaign_name, 'bid_amount': c.bid_amount,
            'total_budget': c.total_budget, 'remaining_budget': c.remaining_budget,
            'impressions': c.impressions, 'clicks': c.clicks, 'spent': c.spent,
            'is_active': c.is_active, 'starts_at': c.starts_at.isoformat(),
            'expires_at': c.expires_at.isoformat() if c.expires_at else None,
        } for c in campaigns]

    def _campaign_detail(self, campaign_id):
        from uds.models import AdCampaign
        try:
            c = AdCampaign.objects.get(uuid=campaign_id, advertiser=self._advertiser)
        except AdCampaign.DoesNotExist:
            raise exceptions.rest.NotFound('Campaign not found')
        return {
            'id': c.uuid, 'name': c.campaign_name, 'bid_amount': c.bid_amount,
            'daily_budget': c.daily_budget, 'total_budget': c.total_budget,
            'remaining_budget': c.remaining_budget, 'impressions': c.impressions,
            'clicks': c.clicks, 'spent': c.spent, 'is_active': c.is_active,
            'targeting': c.targeting, 'ad_content': c.ad_content,
            'starts_at': c.starts_at.isoformat(),
            'expires_at': c.expires_at.isoformat() if c.expires_at else None,
        }

    def _pause_campaign(self, campaign_id):
        from uds.models import AdCampaign
        action = self._params.get('action', 'toggle')
        try:
            c = AdCampaign.objects.get(uuid=campaign_id, advertiser=self._advertiser)
        except AdCampaign.DoesNotExist:
            raise exceptions.rest.NotFound('Campaign not found')
        if action == 'pause':
            c.is_active = False
        elif action == 'resume':
            if c.remaining_budget > 0:
                c.is_active = True
            else:
                raise exceptions.rest.RequestError('Cannot resume campaign with no budget')
        else:
            c.is_active = not c.is_active
        c.save()
        return {'campaign_id': c.uuid, 'is_active': c.is_active}

    def _campaign_analytics(self):
        from uds.models import AdCampaign
        campaigns = AdCampaign.objects.filter(advertiser=self._advertiser)
        total_spent = sum(c.spent for c in campaigns)
        total_impressions = sum(c.impressions for c in campaigns)
        total_clicks = sum(c.clicks for c in campaigns)
        now = timezone.localtime()
        active = sum(1 for c in campaigns if c.is_active and c.remaining_budget > 0)

        return {
            'total_campaigns': campaigns.count(),
            'active_campaigns': active,
            'total_spent': total_spent,
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'ctr': round((total_clicks / total_impressions * 100) if total_impressions > 0 else 0, 2),
            'average_cpm': round((total_spent / total_impressions * 1000) if total_impressions > 0 else 0, 2),
            'generated_at': now.isoformat(),
        }

    def _available_segments(self):
        return {
            'demographics': [
                {'type': 'age_range', 'options': ['13-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+']},
                {'type': 'gender', 'options': ['male', 'female', 'non_binary', 'all']},
                {'type': 'location', 'options': ['Colombia', 'Mexico', 'Brazil', 'Argentina', 'Chile', 'Peru', 'USA', 'Spain']},
                {'type': 'language', 'options': ['es', 'en', 'pt', 'fr', 'de', 'ja', 'ru', 'hi', 'ar', 'ko', 'zh']},
            ],
            'interests': [
                'technology', 'gaming', 'education', 'business', 'design', 'music',
                'sports', 'health', 'travel', 'food', 'fashion', 'entertainment',
                'science', 'finance', 'real_estate', 'automotive',
            ],
            'behavior': [
                {'type': 'device', 'options': ['mobile', 'desktop', 'tablet']},
                {'type': 'frequency', 'options': ['daily', 'weekly', 'monthly']},
                {'type': 'time_of_day', 'options': ['morning', 'afternoon', 'evening', 'night']},
            ],
            'psychographics': [
                'early_adopter', 'price_sensitive', 'brand_loyal', 'convenience_seeker',
                'quality_focused', 'socially_conscious', 'tech_savvy', 'traditional',
            ],
        }

    def _create_api_key(self):
        from uds.models import AdvertiserApiKey, CreditAccount
        account = CreditAccount.objects.get(user=self._advertiser)
        if not account.is_advertiser:
            raise exceptions.rest.RequestError('Not registered as advertiser. Use /coffeepie/credits/ad/register first.')
        key_value = f'cp_ad_{uuid.uuid4().hex[:32]}'
        key = AdvertiserApiKey.objects.create(
            advertiser=self._advertiser, api_key=key_value,
            name=self._params.get('name', f'Key-{uuid.uuid4().hex[:8]}'),
            allowed_origins=self._params.get('allowed_origins', []),
        )
        return {
            'api_key': key.api_key,
            'name': key.name,
            'created': key.created.isoformat(),
        }
