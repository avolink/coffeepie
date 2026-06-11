# -*- coding: utf-8 -*-

#
# Copyright (c) 2026 Virtual Cable S.L.
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

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import dataclasses
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core.ui import gui
from uds.core import transports, types
from uds.core.util.security import convert_to_credential_token
from uds.models import UserService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30

# server: "192.168.1.100",
# port: 3389,
# user: "username",
# password: "password",
# domain: "DOMAIN",
# verify_cert: true,
# use_nla: true,
# screen_width: 1920,
# screen_height: 1080,
# drives_to_redirect: ["C", "D"]


@dataclasses.dataclass
class RDPTunnelParams:
    host: str
    port: int
    ticket: str
    startup_time: int  # In milliseconds


@dataclasses.dataclass
class RDPConnectionParams:
    server: str
    port: int = 3389
    user: str | None = None
    password: str | None = None
    domain: str | None = None
    verify_cert: bool | None = None
    use_nla: bool | None = None
    screen_width: int | None = None
    screen_height: int | None = None
    drives_to_redirect: list[str] | None = None
    tunnel: RDPTunnelParams | None = None

    def as_dict(self) -> dict[str, typing.Any]:
        def _as_dct(v: typing.Any) -> typing.Any:
            if dataclasses.is_dataclass(v) and not isinstance(v, type):
                return dataclasses.asdict(v)
            return v

        # Convert dataclass to dict and remove all empty values
        return {k: _as_dct(v) for k, v in dataclasses.asdict(self).items() if v is not None}


class BaseRDPEmbeddedTransport(transports.Transport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    is_base = True

    PROTOCOL = types.transports.Protocol.RDP
    supported_oss = (types.os.KnownOS.WINDOWS, types.os.KnownOS.LINUX, types.os.KnownOS.MAC_OS)

    force_empty_creds = gui.CheckBoxField(
        label=_('Empty creds'),
        order=11,
        tooltip=_('If checked, the credentials used to connect will be emtpy'),
        tab=types.ui.Tab.CREDENTIALS,
    )
    forced_username = gui.TextField(
        label=_('Username'),
        order=12,
        tooltip=_('If not empty, this username will be always used as credential'),
        tab=types.ui.Tab.CREDENTIALS,
    )
    forced_password = gui.PasswordField(
        label=_('Password'),
        order=13,
        tooltip=_('If not empty, this password will be always used as credential'),
        tab=types.ui.Tab.CREDENTIALS,
    )
    force_no_domain = gui.CheckBoxField(
        label=_('Without Domain'),
        order=14,
        tooltip=_(
            'If checked, the domain part will always be emptied (to connect to xrdp for example is needed)'
        ),
        tab=types.ui.Tab.CREDENTIALS,
    )
    forced_domain = gui.TextField(
        label=_('Domain'),
        order=15,
        tooltip=_('If not empty, this domain will be always used as credential (used as DOMAIN\\user)'),
        tab=types.ui.Tab.CREDENTIALS,
    )
    use_sso = gui.CheckBoxField(
        label=_('Use SSO'),
        order=16,
        default=False,
        tooltip=_(
            'If checked, and user service supports it, will use UDS SSO mechanism. (Ensure you have enabled UDS SSO)'
        ),
        tab=types.ui.Tab.CREDENTIALS,
    )
    use_nla = gui.CheckBoxField(
        label=_('Use NLA'),
        order=20,
        default=True,
        tooltip=_('If checked, Network Level Authentication will be used for RDP connections'),
        tab=types.ui.Tab.PARAMETERS,
    )

    allow_drives = gui.ChoiceField(
        label=_('Local drives policy'),
        order=22,
        tooltip=_('Local drives redirection policy'),
        default='false',
        choices=[
            gui.choice_item('false', 'Allow none'),
            gui.choice_item('dynamic', 'Allow PnP drives'),
            gui.choice_item('true', 'Allow any drive'),
        ],
        tab=types.ui.Tab.PARAMETERS,
    )
    enforce_drives = gui.TextField(
        label=_('Force drives'),
        order=23,
        tooltip=_(
            'Use comma separated values, for example "C:,D:". If drives policy is disallowed, this will be ignored'
        ),
        tab=types.ui.Tab.PARAMETERS,
    )

    rdp_port = gui.NumericField(
        order=30,
        length=5,  # That is, max allowed value is 65535
        label=_('RDP Port'),
        tooltip=_('Use this port as RDP port. Defaults to 3389.'),
        tab=types.ui.Tab.PARAMETERS,
        required=True,  #: Numeric fields have always a value, so this not really needed
        default=3389,
    )

    screen_size = gui.ChoiceField(
        label=_('Screen Size'),
        order=31,
        tooltip=_('Screen size for this transport'),
        default='0x0',
        choices=[
            gui.choice_item('640x480', '640x480'),
            gui.choice_item('800x600', '800x600'),
            gui.choice_item('1024x768', '1024x768'),
            gui.choice_item('1366x768', '1366x768'),
            gui.choice_item('1920x1080', '1920x1080'),
            gui.choice_item('2304x1440', '2304x1440'),
            gui.choice_item('2560x1440', '2560x1440'),
            gui.choice_item('2560x1600', '2560x1600'),
            gui.choice_item('2880x1800', '2880x1800'),
            gui.choice_item('3072x1920', '3072x1920'),
            gui.choice_item('3840x2160', '3840x2160'),
            gui.choice_item('4096x2304', '4096x2304'),
            gui.choice_item('5120x2880', '5120x2880'),
            gui.choice_item('0x0', 'Full screen'),
        ],
        tab=types.ui.Tab.DISPLAY,
    )

    def initialize(self, values: types.core.ValuesType) -> None:
        if not values:
            return

        if self.use_sso.as_bool():
            self.use_nla.value = False  # NLA and SSO are mutually exclusive

    def is_ip_allowed(self, userservice: 'models.UserService', ip: str) -> bool:
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        logger.debug('Checking availability for %s', ip)
        ready = self.cache.get(ip)
        if ready is None:
            # Check again for ready
            if self.test_connectivity(userservice, ip, self.rdp_port.as_int()) is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def processed_username(self, userservice: 'models.UserService', user: 'models.User') -> str:
        v = self.process_user_password(userservice, user, '', alt_username=None)
        return v.username

    def process_user_password(
        self,
        userservice: 'models.UserService',
        user: 'models.User',
        password: str,
        *,
        alt_username: str | None,
    ) -> types.connections.ConnectionData:
        username: str = alt_username or user.get_username_for_auth()

        if self.forced_username.value:
            username = self.forced_username.value

        proc = username.split('@', 1)
        if len(proc) > 1:
            domain = proc[1]
        else:
            domain = ''  # Default domain is empty
        username = proc[0]

        if self.forced_password.value:
            password = self.forced_password.value

        for_azure = False
        forced_domain = self.forced_domain.value.strip().lower()
        if forced_domain:  # If has forced domain
            if forced_domain == 'azuread':
                for_azure = True
            else:
                domain = forced_domain

        if self.force_empty_creds.as_bool():
            username, password, domain = '', '', ''

        if self.force_no_domain.as_bool():
            domain = ''

        if '.' in domain:  # Dotter domain form
            username = username + '@' + domain
            domain = ''

        if for_azure:
            username = 'AzureAD\\' + username  # AzureAD domain form

        # Fix username/password acording to os manager
        username, password = userservice.process_user_password(username, password)

        return types.connections.ConnectionData(
            protocol=self.PROTOCOL,
            username=username,
            service_type=types.services.ServiceType.VDI,
            password=password,
            domain=domain,
        )

    def get_connection_info(
        self,
        userservice: 'models.UserService | models.ServicePool',
        user: 'models.User',
        password: str,
        *,
        for_notify: bool = False,
    ) -> types.connections.ConnectionData:
        username = None
        if isinstance(userservice, UserService):
            cdata = userservice.get_instance().get_connection_data()
            if cdata:
                username = cdata.username or username
                password = cdata.password or password

        cdata = self.process_user_password(
            typing.cast('models.UserService', userservice),
            user,
            password,
            alt_username=username,
        )

        if not for_notify and self.use_sso.as_bool() and isinstance(userservice, UserService):
            cdata = convert_to_credential_token(userservice, cdata)

        return cdata
