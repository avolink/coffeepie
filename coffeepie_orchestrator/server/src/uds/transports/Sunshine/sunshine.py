# -*- coding: utf-8 -*-
#
# Copyright (c) 2025 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
Author: coffeepie_orchestrator integration

Sunshine/Moonlight transport providing ultra-low latency desktop streaming
via GPU-accelerated framebuffer capture and hardware encoding.

Replaces the entire Guacamole HTML5 subsystem:
  - No protocol translation (RDP -> Guacamole protocol -> browser canvas)
  - Hardware-accelerated encode (NVENC/AMF/VAAPI) at ~3-5ms
  - Direct UDP streaming with Reed-Solomon forward error correction
  - Works over Level 2 Private LAN/MAN/WAN (mDNS discovery, no NAT needed)
"""
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds import models
from uds.core import transports, types, ui, consts
from uds.core.util import fields

if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class SunshineTransport(transports.Transport):
    """
    Ultra-low latency streaming via Sunshine (GameStream host) + Moonlight client.

    Sunshine runs on the backend desktop, capturing the framebuffer directly
    via GPU (DXGI/SHM) and encoding with hardware acceleration (NVENC, AMF,
    VAAPI, VideoToolbox). The Moonlight client on the user's device decodes
    via hardware acceleration for sub-16ms end-to-end latency.

    Authentication uses Sunshine's X.509 certificate pairing protocol:
    - First connection: user enters the configured PIN in Moonlight
    - Subsequent connections: trusted via client certificate (automatic)
    - For private L2 networks: PIN can be shared, encryption optional

    Network ports (GameStream protocol, all configurable):
      - 47989/tcp: HTTPS control (serverinfo, pairing, launch)
      - 48010/tcp: RTSP handshake
      - 47998/udp: Control stream (ENet reliable UDP)
      - 47996/udp: Video stream (raw UDP + FEC)
      - 47994/udp: Audio stream (RTP + FEC)
    """

    type_name = _('Sunshine (Moonlight)')
    type_type = 'SunshineTransport'
    type_description = _(
        'Ultra-low latency streaming via Sunshine/Moonlight (GameStream protocol). '
        'GPU-accelerated framebuffer capture with hardware encoding. '
        'Requires Moonlight client on the user device. '
        'Replaces Guacamole HTML5 transport entirely.'
    )
    icon_file = 'sunshine.png'

    own_link = True
    supported_oss = consts.os.DESKTOP_OSS
    PROTOCOL = types.transports.Protocol.OTHER
    group = types.transports.Grouping.DIRECT

    # =====================================================================
    # Configuration Fields
    # =====================================================================

    pairing_pin = ui.gui.TextField(
        label=_('Pairing PIN'),
        order=1,
        tooltip=_(
            '4-digit PIN for Moonlight client pairing. '
            'First connection requires this PIN in the Moonlight client. '
            'After pairing, client certificate is trusted automatically. '
            'For private L2 networks, this can be shared openly.'
        ),
        length=4,
        default='0000',
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='pairingPin',
    )

    sunshine_https_port = ui.gui.NumericField(
        order=10,
        length=5,
        label=_('Sunshine HTTPS Port'),
        tooltip=_(
            'Sunshine GameStream HTTPS control port. Default: 47989. '
            'Other ports (RTSP, video, audio, control) are derived from this.'
        ),
        required=True,
        default=47989,
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='sunshineHttpsPort',
    )

    enable_hdr = ui.gui.CheckBoxField(
        label=_('Enable HDR streaming'),
        order=20,
        tooltip=_('If checked and host GPU supports HDR, HDR content will be streamed.'),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='enableHdr',
    )

    preferred_codec = ui.gui.ChoiceField(
        label=_('Preferred Codec'),
        order=21,
        tooltip=_('Preferred video codec. Host auto-detects best available if set to Auto.'),
        default='auto',
        choices=[
            ui.gui.choice_item('auto', _('Auto-detect (best available)')),
            ui.gui.choice_item('h264', _('H.264 (universal support)')),
            ui.gui.choice_item('hevc', _('HEVC / H.265 (better compression)')),
            ui.gui.choice_item('av1', _('AV1 (best compression, newest)')),
        ],
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='preferredCodec',
    )

    enable_audio = ui.gui.CheckBoxField(
        label=_('Enable Audio'),
        order=22,
        tooltip=_('Stream audio to Moonlight client.'),
        default=True,
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='enableAudio',
    )

    encryption_mode = ui.gui.ChoiceField(
        label=_('Stream Encryption'),
        order=30,
        tooltip=_(
            'Encryption mode for video/audio streams. '
            'For private L2 networks, "Never" eliminates encryption overhead. '
            'AES-GCM has negligible overhead on modern CPUs with AES-NI.'
        ),
        default='opportunistic',
        choices=[
            ui.gui.choice_item('never', _('Never (no encryption, lowest latency)')),
            ui.gui.choice_item('opportunistic', _('Opportunistic (encrypt if client supports)')),
            ui.gui.choice_item('mandatory', _('Mandatory (require encryption)')),
        ],
        tab=types.ui.Tab.ADVANCED,
        old_field_name='encryptionMode',
    )

    # =====================================================================
    # Transport Implementation
    # =====================================================================

    def is_ip_allowed(self, userservice: 'models.UserService', ip: str) -> bool:
        """Check if Sunshine host is reachable on HTTPS control port."""
        logger.debug('Checking Sunshine availability for %s', ip)
        ready = self.cache.get(ip)
        if not ready:
            if self.test_connectivity(
                userservice, ip, self.sunshine_https_port.as_int()
            ):
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def processed_username(
        self, userservice: 'models.UserService', user: 'models.User'
    ) -> str:
        return user.get_username_for_auth()

    def get_connection_info(
        self,
        userservice: 'models.UserService | models.ServicePool',
        user: 'models.User',
        password: str,
        *,
        for_notify: bool = False,
    ) -> types.connections.ConnectionData:
        username = user.get_username_for_auth()

        if isinstance(userservice, models.UserService):
            cdata = userservice.get_instance().get_connection_data()
            if cdata:
                username = cdata.username or username
                password = cdata.password or password

        username, password = userservice.process_user_password(username, password)

        return types.connections.ConnectionData(
            protocol=self.PROTOCOL,
            username=username,
            service_type=types.services.ServiceType.VDI,
            password=password,
            domain='',
        )

    def get_link(
        self,
        userservice: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> str:
        """
        Returns a broker-hosted launch page URL for Sunshine/Moonlight.

        The page shows connection info (host, port, PIN) and auto-launches
        Moonlight via the moonlight:// protocol handler. Falls back to
        manual instructions if Moonlight is not installed.

        Uses TicketStore to securely pass connection parameters to the page.
        """
        # Store connection params in a secure ticket
        params: dict[str, typing.Any] = {
            'host': ip,
            'port': self.sunshine_https_port.as_int(),
            'pin': self.pairing_pin.value,
            'codec': self.preferred_codec.value,
            'hdr': self.enable_hdr.as_bool(),
            'audio': self.enable_audio.as_bool(),
            'encryption': self.encryption_mode.value,
        }

        ticket = models.TicketStore.create(
            params, validity=self.ticket_validity.as_int()
        )

        from django.urls import reverse

        return str(
            request.build_absolute_uri(
                reverse('webapi.sunshine_launch', args=(ticket,))
            )
        )
