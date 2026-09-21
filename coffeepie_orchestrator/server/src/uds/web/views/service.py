# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.
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
import json
import logging
import typing
import collections.abc

from django.utils.translation import gettext
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from uds import models
from uds.core import types
from uds.core.auths import auth
from uds.core.auths.auth import weblogin_required, get_webpassword
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.userservice import UserServiceManager
from uds.core.types.requests import ExtendedHttpRequest
from uds.core.util import log
from uds.core.exceptions.services import ServiceNotReadyError, MaxServicesReachedError, ServiceAccessDeniedByCalendar

from uds.web.util import services
from uds.web.util.services import get_services_info_dict
from uds.web.views.main import logger

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser
    from uds.models import UserService

logger = logging.getLogger(__name__)


@weblogin_required()
def transport_own_link(
    request: 'ExtendedHttpRequestWithUser', service_id: str, transport_id: str
) -> HttpResponse:
    def _response(url: str = '', percent: int = 100, error: typing.Any = '') -> dict[str, typing.Any]:
        return {'running': percent, 'url': url, 'error': str(error)}
    
    response: dict[str, typing.Any] = {}

    try:
        info = UserServiceManager.manager().get_user_service_info(
            request.user, request.os, request.ip, service_id, transport_id
        )
        # ip, userService, _iads, trans, itrans = res
        # This returns a response object in fact
        if info.ip:
            response = _response(
                url=info.transport.get_instance().get_link(
                    info.userservice,
                    info.transport,
                    info.ip,
                    request.os,
                    request.user,
                    get_webpassword(request),
                    request,
                ),
            )
    except ServiceNotReadyError as e:
        logger.debug('Service not ready')
        # Not ready, show message and return to this page in a while
        # error += ' (code {0:04X})'.format(e.code)
        response = _response(percent=e.code)
    except MaxServicesReachedError:
        logger.info('Number of service reached MAX for service pool "%s"', service_id)
        response = _response(error=types.errors.Error.MAX_SERVICES_REACHED.message)
    except ServiceAccessDeniedByCalendar:
        logger.info('Access tried to a calendar limited access pool "%s"', service_id)
        response = _response(error=types.errors.Error.SERVICE_CALENDAR_DENIED.message)
    except Exception as e:
        logger.exception('Error')
        response = _response(error=gettext('Internal error'))
        
    return HttpResponse(content=json.dumps(response), content_type='application/json')


@weblogin_required()
@never_cache
def user_service_enabler(
    request: 'ExtendedHttpRequestWithUser', service_id: str, transport_id: str
) -> HttpResponse:
    return HttpResponse(
        json.dumps(services.enable_service(request, service_id=service_id, transport_id=transport_id)),
        content_type='application/json',
    )


def closer(request: 'ExtendedHttpRequest') -> HttpResponse:
    """Returns a page that closes itself (used by transports)"""
    return HttpResponse(
        '<html><head><script>window.close();</script></head><body></body></html>',
        content_type='text/html',
    )
    # return HttpResponse('<html><body onload="window.close()"></body></html>')


@weblogin_required()
@never_cache
def user_service_status(
    request: 'ExtendedHttpRequestWithUser', service_id: str, transport_id: str
) -> HttpResponse:
    '''
    Returns;
     'running' if not ready
     'ready' if is ready but not accesed by client
     'accessed' if ready and accesed by UDS client
     'error' if error is found (for example, intancing user service)
    Note:
    '''
    ip: str |  None | bool
    userservice: 'UserService | None' = None
    status = 'running'
    # If service exists (meta or not)
    if UserServiceManager.manager().is_meta_service(service_id):
        userservice = UserServiceManager.manager().locate_meta_service(user=request.user, id_metapool=service_id)
    else:
        userservice = UserServiceManager.manager().locate_user_service(
            user=request.user, userservice_id=service_id, create=False
        )
    if userservice:
        # Service exists...
        try:
            userservice_instance = userservice.get_instance()
            ip = userservice_instance.get_ip()
            userservice.log_ip(ip)
            # logger.debug('Res: %s %s %s %s %s', ip, userService, userServiceInstance, transport, transportInstance)
        except ServiceNotReadyError:
            ip = None
        except Exception:
            ip = False

        ready = 'ready'
        if userservice.properties.get('accessed_by_client', False) is True:
            ready = 'accessed'

        status = 'running' if ip is None else 'error' if ip is False else ready

    return HttpResponse(json.dumps({'status': status}), content_type='application/json')


@weblogin_required()
@never_cache
def action(request: 'ExtendedHttpRequestWithUser', service_id: str, action_string: str) -> HttpResponse:
    # favorite/unfavorite do not require an existing UserService,
    # so handle them before the userservice lookup.
    # service_id is 'F<pool_uuid>' or 'M<meta_uuid>' — strip the prefix.
    if action_string in ('favorite', 'unfavorite'):
        pool_uuid = service_id[1:]
        if action_string == 'favorite':
            request.user.add_favorite(pool_uuid)
        else:
            request.user.remove_favorite(pool_uuid)
        return HttpResponse(json.dumps(None), content_type='application/json')

    userservice = UserServiceManager.manager().locate_meta_service(request.user, service_id)
    if not userservice:
        userservice = UserServiceManager.manager().locate_user_service(request.user, service_id, create=False)

    response: typing.Any = None
    rebuild: bool = False
    if userservice:
        match action_string:
            case 'release':
                if userservice.service_pool.allow_users_remove:
                    rebuild = True
                    log.log(
                        userservice.service_pool,
                        types.log.LogLevel.INFO,
                        "Removing User Service {} as requested by {} from {}".format(
                            userservice.friendly_name, request.user.pretty_name, request.ip
                        ),
                        types.log.LogSource.WEB,
                    )
                    UserServiceManager.manager().request_logoff(userservice)
                    userservice.release()
            case 'reset':
                if userservice.service_pool.allow_users_reset and userservice.service_pool.service.get_type().can_reset:
                    logger.info('Resetting service')
                    rebuild = True
                    log.log(
                        userservice.service_pool,
                        types.log.LogLevel.INFO,
                        "Reseting User Service {} as requested by {} from {}".format(
                            userservice.friendly_name, request.user.pretty_name, request.ip
                        ),
                        types.log.LogSource.WEB,
                    )
                    UserServiceManager.manager().reset(userservice)
            case _:
                log.log(
                    userservice.service_pool,
                    types.log.LogLevel.ERROR,
                    "Unknown action '{}' requested by {} from {}".format(action_string, request.user.pretty_name, request.ip),
                    types.log.LogSource.WEB,
                )

    if rebuild:
        for v in services.get_services_info_dict(request)['services']:
            if v['id'] == service_id:
                response = v
                break

    return HttpResponse(json.dumps(response), content_type='application/json')

@never_cache
@auth.deny_non_authenticated  # web_login_required not used here because this is not a web page, but js
def services_data_json(request: types.requests.ExtendedHttpRequestWithUser) -> HttpResponse:
    return JsonResponse(get_services_info_dict(request))


@csrf_exempt
@auth.deny_non_authenticated
def update_transport_ticket(
    request: types.requests.ExtendedHttpRequestWithUser, ticket_id: str, scrambler: str
) -> HttpResponse:
    try:
        if request.method == 'POST':
            # Get request body as json
            data: dict[str, str] = json.loads(request.body)

            # Update username andd password in ticket
            username = data.get('username', None) or None  # None if not present
            password: 'str|bytes|None' = (
                data.get('password', None) or None
            )  # If password is empty, set it to None
            domain = data.get('domain', None) or None  # If empty string, set to None
            if domain and '.' in domain:
                username = f'{username}@{domain}'
                domain = None

            if password:
                password = CryptoManager.manager().symmetric_encrypt(password, scrambler)

            def _is_ticket_valid(data: collections.abc.Mapping[str, typing.Any]) -> bool:
                if 'ticket-info' in data:
                    try:
                        user = models.User.objects.get(
                            uuid=typing.cast(dict[str, str], data['ticket-info']).get('user', None)
                        )
                        if request.user != user:
                            return False
                    except models.User.DoesNotExist:
                        return False

                    if username:
                        try:
                            userservice = models.UserService.objects.get(
                                uuid=data['ticket-info'].get('userService', None)
                            )
                            UserServiceManager.manager().notify_preconnect(
                                userservice,
                                types.connections.ConnectionData(
                                    username=username,
                                    protocol=data.get('protocol', ''),
                                    service_type=data['ticket-info'].get('service_type', ''),
                                ),
                            )
                        except models.UserService.DoesNotExist:
                            pass

                return True

            models.TicketStore.update(
                uuid=ticket_id,
                checking_fnc=_is_ticket_valid,
                username=username,
                password=password,
                domain=domain,
            )
            return HttpResponse('{"status": "OK"}', status=200, content_type='application/json')
    except Exception as e:
        # fallback to error
        logger.warning('Error updating ticket: %s', e)

    # Invalid request
    return HttpResponse('{"status": "Invalid Request"}', status=400, content_type='application/json')


@never_cache
def sunshine_launch(request: 'ExtendedHttpRequestWithUser', ticket_id: str) -> HttpResponse:
    """
    Serves the Sunshine/Moonlight launch page.

    Reads connection parameters from a TicketStore and renders an HTML page
    that shows pairing info and auto-launches the Moonlight client via the
    moonlight:// protocol handler.
    """
    try:
        ticket_data = models.TicketStore.get(ticket_id)
        if not ticket_data:
            return HttpResponse(
                '<html><body><h1>Session Expired</h1>'
                '<p>This connection session has expired. Please reconnect from UDS.</p>'
                '</body></html>',
                content_type='text/html',
                status=410,
            )

        host = ticket_data.get('host', '')
        port = ticket_data.get('port', 47989)
        pin = ticket_data.get('pin', '0000')

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sunshine Connection</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    display: flex; justify-content: center; align-items: center;
    min-height: 100vh; padding: 20px;
  }}
  .container {{
    background: #16213e; border-radius: 16px; padding: 40px;
    max-width: 480px; width: 100%%; text-align: center;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  }}
  h1 {{ color: #f5c518; margin-bottom: 8px; font-size: 28px; }}
  .subtitle {{ color: #888; margin-bottom: 32px; font-size: 14px; }}
  .info-box {{
    background: #0f3460; border-radius: 12px; padding: 24px;
    margin-bottom: 24px; text-align: left;
  }}
  .info-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #1a1a4e; }}
  .info-row:last-child {{ border-bottom: none; }}
  .info-label {{ color: #888; font-size: 13px; }}
  .info-value {{ color: #f5c518; font-family: monospace; font-size: 15px; font-weight: bold; }}
  .pin-display {{
    background: #0a0a1e; border: 2px dashed #f5c518;
    border-radius: 10px; padding: 16px; margin: 20px 0;
    font-size: 36px; letter-spacing: 8px; font-family: monospace;
    color: #f5c518; font-weight: bold;
  }}
  .btn {{
    display: inline-block; background: #f5c518; color: #1a1a2e;
    border: none; border-radius: 8px; padding: 14px 40px;
    font-size: 16px; font-weight: bold; cursor: pointer;
    text-decoration: none; transition: background 0.2s;
  }}
  .btn:hover {{ background: #ffd700; }}
  .manual {{ margin-top: 24px; color: #666; font-size: 12px; line-height: 1.6; }}
  .manual code {{ color: #aaa; background: #0a0a1e; padding: 2px 6px; border-radius: 4px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Sunshine Streaming</h1>
  <p class="subtitle">Ultra-low latency via GPU framebuffer capture</p>

  <div class="info-box">
    <div class="info-row">
      <span class="info-label">Host</span>
      <span class="info-value">{host}:{port}</span>
    </div>
    <div class="info-row">
      <span class="info-label">Protocol</span>
      <span class="info-value">GameStream</span>
    </div>
    <div class="info-row">
      <span class="info-label">Stream</span>
      <span class="info-value">Direct P2P (UDP)</span>
    </div>
  </div>

  <div class="pin-display">{pin}</div>
  <p style="color:#888;margin-bottom:20px;font-size:13px;">Pairing PIN — enter this in Moonlight on first connection</p>

  <a href="moonlight://{host}:{port}" class="btn" id="launch-btn">
    Launch Moonlight
  </a>

  <div class="manual">
    <p>If Moonlight does not launch automatically:</p>
    <p>1. Open <strong>Moonlight</strong> on your device</p>
    <p>2. Add host: <code>{host}</code></p>
    <p>3. Enter PIN: <code>{pin}</code> when prompted</p>
    <p style="margin-top:8px;">After pairing, future connections are automatic.</p>
  </div>
</div>

<script>
  window.onload = function() {{
    var a = document.getElementById('launch-btn');
    a.click();
    setTimeout(function() {{
      window.close();
    }}, 1500);
  }};
</script>
</body>
</html>'''

        return HttpResponse(html, content_type='text/html')

    except Exception as e:
        logger.error('Error in sunshine_launch: %s', e)
        return HttpResponse(
            '<html><body><h1>Connection Error</h1>'
            '<p>Could not retrieve connection information. Please try again.</p>'
            '</body></html>',
            content_type='text/html',
            status=500,
        )
