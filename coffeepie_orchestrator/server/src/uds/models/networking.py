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
Models for NAT traversal, GeoDNS, and certified device registry.

Components:
- CertifiedDevice: registered codec terminals with hardware fingerprints
- TurnServer: TURN server configuration per region
- OrchestratorRegion: GeoDNS mapping (region -> orchestrator URL)
- NatSession: active NAT traversal sessions
- NetworkAccess: per-user network access tier (L2/L3/L4)
"""
import logging
import typing

from django.db import models

from .uuid_model import UUIDModel
from ..core.util.model import sql_now

if typing.TYPE_CHECKING:
    from uds.models import User

logger = logging.getLogger(__name__)


class NetworkTier(models.TextChoices):
    L2 = 'L2', 'Layer 2 - Private LAN (Certified)'
    L3 = 'L3', 'Layer 3 - Internet via Relay'
    L4 = 'L4', 'Layer 4 - WebRTC Fallback'


class CertifiedDevice(UUIDModel):
    mac_address = models.CharField(max_length=17, unique=True, db_index=True)
    serial_number = models.CharField(max_length=128, unique=True, db_index=True)
    model_name = models.CharField(max_length=64)
    manufacturer = models.CharField(max_length=128)
    firmware_version = models.CharField(max_length=32, blank=True, default='')
    public_key = models.TextField(blank=True, default='')
    owner = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_devices')
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    network_tier = models.CharField(max_length=2, choices=NetworkTier.choices, default=NetworkTier.L2)
    last_seen = models.DateTimeField(default=sql_now)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    geo_region = models.CharField(max_length=8, blank=True, default='')
    registered_at = models.DateTimeField(default=sql_now)

    class Meta(UUIDModel.Meta):
        db_table = 'uds_certified_devices'
        app_label = 'uds'
        ordering = ('-registered_at',)

    def __str__(self) -> str:
        return f'Device {self.model_name} ({self.mac_address[:17]})'


class TurnServer(UUIDModel):
    region = models.CharField(max_length=8, db_index=True)
    hostname = models.CharField(max_length=256)
    port = models.PositiveIntegerField(default=3478)
    tls_port = models.PositiveIntegerField(default=5349)
    username_prefix = models.CharField(max_length=32)
    shared_secret = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveSmallIntegerField(default=0)
    created = models.DateTimeField(default=sql_now)

    class Meta(UUIDModel.Meta):
        db_table = 'uds_turn_servers'
        app_label = 'uds'
        ordering = ('-priority',)

    def __str__(self) -> str:
        return f'TURN {self.region}: {self.hostname}:{self.port}'


class OrchestratorRegion(UUIDModel):
    region = models.CharField(max_length=8, unique=True, db_index=True)
    name = models.CharField(max_length=64)
    orchestrator_url = models.URLField(max_length=512)
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    priority = models.PositiveSmallIntegerField(default=0)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    created = models.DateTimeField(default=sql_now)

    class Meta(UUIDModel.Meta):
        db_table = 'uds_orchestrator_regions'
        app_label = 'uds'
        ordering = ('-priority', '-is_primary')

    def __str__(self) -> str:
        return f'{self.region}: {self.name} -> {self.orchestrator_url}'


class NatSession(UUIDModel):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='nat_sessions')
    device = models.ForeignKey(CertifiedDevice, on_delete=models.SET_NULL, null=True, blank=True)
    turn_server = models.ForeignKey(TurnServer, on_delete=models.SET_NULL, null=True, blank=True)
    local_ip = models.GenericIPAddressField()
    public_ip = models.GenericIPAddressField(null=True, blank=True)
    local_port = models.PositiveIntegerField()
    public_port = models.PositiveIntegerField(null=True, blank=True)
    turn_username = models.CharField(max_length=128, blank=True, default='')
    turn_password = models.CharField(max_length=128, blank=True, default='')
    network_tier = models.CharField(max_length=2, choices=NetworkTier.choices)
    created = models.DateTimeField(default=sql_now)
    expires_at = models.DateTimeField()

    class Meta(UUIDModel.Meta):
        db_table = 'uds_nat_sessions'
        app_label = 'uds'

    def __str__(self) -> str:
        return f'NAT session for {self.user.pretty_name} ({self.network_tier})'
