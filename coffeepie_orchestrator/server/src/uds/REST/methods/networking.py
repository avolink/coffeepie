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
Coffee Pie Networking REST API.

Routes (under /coffeepie/network/):
  GET  orchestrators      -> Get orchestrator fallback list (GeoDNS)
  POST device/register    -> Register a certified codec terminal
  POST device/verify      -> Verify device certification status
  POST turn/credentials   -> Allocate TURN credentials for NAT traversal
  POST session/start      -> Start a NAT traversal session
  GET  session/status     -> Check current NAT session status
"""
import datetime
import hashlib
import hmac
import logging
import typing
import time

from django.utils import timezone
from django.db import transaction as db_transaction
from django.core.exceptions import ObjectDoesNotExist

from uds.core import consts, exceptions
from uds.REST import Handler

logger = logging.getLogger(__name__)


def _generate_turn_credentials(secret, username_prefix, ttl_seconds=86400):
    timestamp = int(time.time()) + ttl_seconds
    username = f'{timestamp}:{username_prefix}'
    password = hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()
    password_b64 = __import__('base64').b64encode(password).decode()
    return username, password_b64


class Network(Handler):
    PATH = 'coffeepie'

    def get(self) -> typing.Any:
        args = self._args
        if not args:
            raise exceptions.rest.RequestError('Missing operation')

        op = args[0].lower()

        if op == 'orchestrators':
            return self._get_orchestrators()
        if op == 'session' and len(args) >= 2:
            if args[1].lower() == 'status':
                return self._session_status()
        raise exceptions.rest.RequestError(f'Unknown operation: {"/".join(args)}')

    def post(self) -> typing.Any:
        args = self._args
        if not args:
            raise exceptions.rest.RequestError('Missing operation')

        op = args[0].lower()

        if op == 'device' and len(args) >= 2:
            sub = args[1].lower()
            if sub == 'register':
                return self._register_device()
            if sub == 'verify':
                return self._verify_device()
        if op == 'turn' and len(args) >= 2:
            if args[1].lower() == 'credentials':
                return self._turn_credentials()
        if op == 'session' and len(args) >= 2:
            if args[1].lower() == 'start':
                return self._session_start()

        raise exceptions.rest.RequestError(f'Unknown operation: {"/".join(args)}')

    def _get_orchestrators(self):
        from uds.models import OrchestratorRegion
        regions = OrchestratorRegion.objects.filter(is_active=True).order_by('-is_primary', '-priority')
        return [{
            'region': r.region, 'name': r.name, 'url': r.orchestrator_url,
            'is_primary': r.is_primary, 'priority': r.priority,
            'latitude': r.latitude, 'longitude': r.longitude,
        } for r in regions]

    def _register_device(self):
        from uds.models import CertifiedDevice, CreditAccount
        mac = self._params.get('mac_address', '').strip()
        serial = self._params.get('serial_number', '').strip()
        model_name = self._params.get('model_name', '')
        manufacturer = self._params.get('manufacturer', '')
        public_key = self._params.get('public_key', '')
        if not mac or not serial:
            raise exceptions.rest.RequestError('mac_address and serial_number are required')
        if len(mac) < 12:
            raise exceptions.rest.RequestError('Invalid MAC address')
        pk = {"mac": mac, "serial": serial}
        device, created = CertifiedDevice.objects.get_or_create(
            mac_address=mac, defaults={
                'serial_number': serial, 'model_name': model_name,
                'manufacturer': manufacturer, 'firmware_version': self._params.get('firmware_version', ''),
                'public_key': public_key, 'owner': self._user,
                'is_verified': False, 'last_seen': timezone.localtime(),
                'last_ip': self._request.ip,
            }
        )
        if not created:
            device.last_seen = timezone.localtime()
            device.last_ip = self._request.ip
            device.firmware_version = self._params.get('firmware_version', device.firmware_version)
            device.save(update_fields=['last_seen', 'last_ip', 'firmware_version'])
        account = CreditAccount.objects.get(user=self._user)
        device.network_tier = 'L3' if account.balance == 0 else 'L2'
        device.save(update_fields=['network_tier'])
        return {
            'device_id': device.uuid, 'is_new': created, 'is_verified': device.is_verified,
            'network_tier': device.network_tier,
        }

    def _verify_device(self):
        from uds.models import CertifiedDevice
        mac = self._params.get('mac_address', '').strip()
        if not mac:
            raise exceptions.rest.RequestError('mac_address is required')
        try:
            device = CertifiedDevice.objects.get(mac_address=mac)
        except CertifiedDevice.DoesNotExist:
            return {'verified': False, 'registered': False}
        return {
            'verified': device.is_verified, 'registered': True,
            'network_tier': device.network_tier, 'model': device.model_name,
        }

    def _turn_credentials(self):
        from uds.models import TurnServer, CreditAccount
        region = self._params.get('region', 'CO-01')
        account = CreditAccount.objects.get(user=self._user)
        is_free = account.balance == 0
        server = TurnServer.objects.filter(is_active=True, region=region).first()
        if not server:
            server = TurnServer.objects.filter(is_active=True).first()
        if not server:
            return {'available': False, 'reason': 'No TURN servers available'}
        username, password = _generate_turn_credentials(server.shared_secret, server.username_prefix)
        return {
            'available': True,
            'uris': [f'turn:{server.hostname}:{server.port}?transport=udp', f'turns:{server.hostname}:{server.tls_port}?transport=tcp'],
            'username': username, 'password': password,
            'ttl': 86400, 'network_tier': 'L3' if is_free else 'L2',
        }

    def _session_start(self):
        from uds.models import NatSession, CertifiedDevice, TurnServer, CreditAccount, NetworkTier
        mac = self._params.get('mac_address', '')
        local_ip = self._params.get('local_ip', '')
        local_port = int(self._params.get('local_port', 0))
        if not local_ip or not local_port:
            raise exceptions.rest.RequestError('local_ip and local_port are required')
        with db_transaction.atomic():
            account = CreditAccount.objects.get(user=self._user)
            tier = NetworkTier.L3 if account.balance == 0 else NetworkTier.L2
            device = None
            if mac:
                try:
                    device = CertifiedDevice.objects.get(mac_address=mac)
                except CertifiedDevice.DoesNotExist:
                    pass
            if tier == NetworkTier.L2 and (not device or not device.is_verified):
                tier = NetworkTier.L3
            turn = None
            turn_user = ''
            turn_pass = ''
            if tier != NetworkTier.L2:
                turn = TurnServer.objects.filter(is_active=True).first()
                if turn:
                    turn_user, turn_pass = _generate_turn_credentials(turn.shared_secret, turn.username_prefix)
            public_ip = self._request.ip
            expires = timezone.localtime() + datetime.timedelta(hours=6)
            sess = NatSession.objects.create(
                user=self._user, device=device, turn_server=turn,
                local_ip=local_ip, public_ip=public_ip, local_port=local_port,
                public_port=local_port, turn_username=turn_user, turn_password=turn_pass,
                network_tier=tier, expires_at=expires,
            )
        result = {
            'session_id': sess.uuid, 'network_tier': tier,
            'public_ip': sess.public_ip, 'public_port': sess.public_port,
            'expires_at': sess.expires_at.isoformat(),
        }
        if turn:
            result['turn'] = {
                'host': turn.hostname, 'port': turn.port, 'tls_port': turn.tls_port,
                'username': turn_user, 'password': turn_pass,
            }
        return result

    def _session_status(self):
        from uds.models import NatSession
        now = timezone.localtime()
        sess = NatSession.objects.filter(user=self._user, expires_at__gt=now).order_by('-created').first()
        if not sess:
            return {'active': False}
        return {
            'active': True, 'session_id': sess.uuid, 'network_tier': sess.network_tier,
            'public_ip': sess.public_ip, 'public_port': sess.public_port,
            'expires_at': sess.expires_at.isoformat(),
        }
