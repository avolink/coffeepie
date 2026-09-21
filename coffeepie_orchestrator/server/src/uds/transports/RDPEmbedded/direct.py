# -*- coding: utf-8 -*-

#
# Copyright (c) 2026 Virtual Cable S.L.
# All rights reservem.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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

'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import types

from .common import BaseRDPEmbeddedTransport, RDPConnectionParams

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class RDPEmbeddedTransport(BaseRDPEmbeddedTransport):
    '''
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''

    is_base = False

    type_name = _('Embedded RDP Client')
    type_type = 'RDPEmbeddedTransport'
    type_description = _('RDP Embedded Client. Direct connection.')
    icon_file = 'rdp.png'

    force_empty_creds = BaseRDPEmbeddedTransport.force_empty_creds
    forced_username = BaseRDPEmbeddedTransport.forced_username
    forced_password = BaseRDPEmbeddedTransport.forced_password
    force_no_domain = BaseRDPEmbeddedTransport.force_no_domain
    forced_domain = BaseRDPEmbeddedTransport.forced_domain
    use_sso = BaseRDPEmbeddedTransport.use_sso

    allow_drives = BaseRDPEmbeddedTransport.allow_drives
    enforce_drives = BaseRDPEmbeddedTransport.enforce_drives
    use_nla = BaseRDPEmbeddedTransport.use_nla
    use_sso = BaseRDPEmbeddedTransport.use_sso
    rdp_port = BaseRDPEmbeddedTransport.rdp_port

    screen_size = BaseRDPEmbeddedTransport.screen_size

    def get_transport_script(  # pylint: disable=too-many-locals
        self,
        userservice: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> 'types.transports.TransportScript':
        # We use helper to keep this clean

        ci = self.get_connection_info(userservice, user, password)
        width, height = self.screen_size.value.split('x')
        drives_to_redirect = (
            None
            if not self.allow_drives.as_bool()
            else (
                ["all"]
                if not self.enforce_drives.as_bool()
                else (
                    ["fixed"]
                    if not self.enforce_drives.value.strip()
                    else [d.strip() for d in self.enforce_drives.value.split(',')]
                )
            )
        )

        data = RDPConnectionParams(
            server=ip,
            port=self.rdp_port.value,
            user=ci.username,
            password=ci.password if not self.use_sso.as_bool() else '__NO_PASSWORD__',
            domain=ci.domain if not self.use_sso.as_bool() else 'UDS',
            verify_cert=False,
            use_nla=self.use_nla.as_bool(),
            screen_width=int(width),
            screen_height=int(height),
            drives_to_redirect=drives_to_redirect,
        )
        if os.os not in (types.os.KnownOS.WINDOWS, types.os.KnownOS.LINUX, types.os.KnownOS.MAC_OS):
            logger.error(
                'Os not valid for RDP Transport: %s',
                request.META.get('HTTP_USER_AGENT', 'Unknown'),
            )
            return super().get_transport_script(
                userservice,
                transport,
                ip,
                os,
                user,
                password,
                request,
            )

        return self.get_script(os.os.os_name(), 'direct', data.as_dict())
