# -*- coding: utf-8 -*-

#
# Copyright (c) 2024-2025 Coffee Pie S.A.S. BIC
# All rights reserved.

"""
Advertiser Dashboard views.

Routes:
  /uds/page/advertiser/           -> Dashboard overview
  /uds/page/advertiser/campaigns  -> Campaign list + create
  /uds/page/advertiser/keys       -> API key management
  /uds/page/advertiser/analytics  -> Performance analytics
"""
import datetime
import logging

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from uds.models import (
    AdCampaign, AdvertiserApiKey, CreditAccount, TransactionType,
    User,
)
from uds.core.auths.auth import root_user

logger = logging.getLogger(__name__)


def _get_advertiser(request):
    if not request.user.is_authenticated:
        return None
    try:
        account = CreditAccount.objects.get(user=request.user)
    except CreditAccount.DoesNotExist:
        return None
    return request.user if account.is_advertiser else None


def _ctx(request, **extra):
    advertiser = _get_advertiser(request)
    account = CreditAccount.objects.get(user=request.user) if request.user.is_authenticated else None
    return {
        'request': request,
        'advertiser': advertiser,
        'account': account,
        'balance': account.balance if account else 0,
        **extra,
    }


def dashboard(request: HttpRequest) -> HttpResponse:
    advertiser = _get_advertiser(request)
    if not advertiser:
        return render(request, 'uds/advertiser/not_advertiser.html', status=403)

    account = CreditAccount.objects.get(user=advertiser)
    campaigns = AdCampaign.objects.filter(advertiser=advertiser).order_by('-created')
    active = campaigns.filter(is_active=True, remaining_budget__gt=0).count()
    total_spent = sum(c.spent for c in campaigns)
    total_impressions = sum(c.impressions for c in campaigns)
    total_clicks = sum(c.clicks for c in campaigns)

    return render(request, 'uds/advertiser/dashboard.html', {
        **_ctx(request, advertiser=advertiser, account=account),
        'campaigns': campaigns[:10],
        'active_count': active,
        'total_campaigns': campaigns.count(),
        'total_spent': total_spent,
        'total_impressions': total_impressions,
        'total_clicks': total_clicks,
        'ctr': round((total_clicks / total_impressions * 100) if total_impressions > 0 else 0, 2),
    })


def campaigns(request: HttpRequest) -> HttpResponse:
    advertiser = _get_advertiser(request)
    if not advertiser:
        return render(request, 'uds/advertiser/not_advertiser.html', status=403)

    campaigns = AdCampaign.objects.filter(advertiser=advertiser).order_by('-created')
    return render(request, 'uds/advertiser/campaigns.html', {
        **_ctx(request),
        'campaigns': campaigns,
    })


def api_keys(request: HttpRequest) -> HttpResponse:
    advertiser = _get_advertiser(request)
    if not advertiser:
        return render(request, 'uds/advertiser/not_advertiser.html', status=403)

    keys = AdvertiserApiKey.objects.filter(advertiser=advertiser).order_by('-created')
    return render(request, 'uds/advertiser/api_keys.html', {
        **_ctx(request),
        'api_keys': keys,
    })


def analytics(request: HttpRequest) -> HttpResponse:
    advertiser = _get_advertiser(request)
    if not advertiser:
        return render(request, 'uds/advertiser/not_advertiser.html', status=403)

    campaigns = AdCampaign.objects.filter(advertiser=advertiser).order_by('-created')
    total_spent = sum(c.spent for c in campaigns)
    total_impressions = sum(c.impressions for c in campaigns)
    total_clicks = sum(c.clicks for c in campaigns)

    return render(request, 'uds/advertiser/analytics.html', {
        **_ctx(request),
        'campaigns': campaigns,
        'total_spent': total_spent,
        'total_impressions': total_impressions,
        'total_clicks': total_clicks,
        'ctr': round((total_clicks / total_impressions * 100) if total_impressions > 0 else 0, 2),
        'cpm': round((total_spent / total_impressions * 1000) if total_impressions > 0 else 0, 2),
    })


@require_http_methods(["POST"])
def register_advertiser(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return HttpResponse('Not authenticated', status=401)
    account = CreditAccount.objects.get(user=request.user)
    account.is_advertiser = True
    account.advertiser_name = request.POST.get('advertiser_name', request.user.pretty_name)
    account.advertiser_segments = request.POST.get('segments', '[]')
    account.save(update_fields=['is_advertiser', 'advertiser_name', 'advertiser_segments'])
    return HttpResponseRedirect('/uds/page/advertiser/')
