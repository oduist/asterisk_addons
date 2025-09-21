# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2024
from datetime import datetime, timedelta
import hashlib
import json
import requests
from requests.compat import urljoin
from urllib.parse import urlencode
from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.addons.asterisk_plus.models.settings import debug

GS_HEADERS = {
    'Content-Type': 'application/json',
    'Connection': 'close'
}

# Disable warnings for insecure connections
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)


class gsSettings(models.Model):
    _inherit = 'asterisk_plus.server'

    gs_api_url = fields.Char('API URL',)
    gs_api_user = fields.Char('API User',)
    gs_api_password = fields.Char('API Password')
    gs_cookie_expire_time = fields.Datetime()
    gs_cookie = fields.Char()
    gs_model = fields.Selection([
        ('ucm', 'UCMXXXX'),
        ], string='Model', default='ucm')
    gs_api_version = fields.Selection([
        ('1.0', '1.0'),
        ], string='API version', default='1.0')
    gs_verify_ssl = fields.Boolean(string='Verify SSL', default=False)
    gs_model_name = fields.Char('Model Name', readonly=True)
    gs_system_time = fields.Char('System Time', readonly=True)
    gs_uptime = fields.Char('Uptime', readonly=True)

    def gs_api_request(self, action, data={}, refresh_cookie=False, return_json=True):
        # Set refresh count in order to protect from recursion
        self.ensure_one()
        # Check for cached token
        if not refresh_cookie and self.gs_cookie_expire_time:
            expire_seconds = (self.gs_cookie_expire_time - datetime.now()).total_seconds()
            if expire_seconds > 0:
                debug(self, 'GS: using cached access token.')
                cookie = self.gs_cookie
            else:
                cookie = self.gs_get_cookie()                
        else:
            cookie = self.gs_get_cookie()
        request_url = '{}/api'.format(self.gs_api_url)
        request_data = {
            'request': {
                'action': action,
                'cookie': cookie
            }
        }
        request_data['request'].update(data)
        response = requests.post(
            request_url, headers=GS_HEADERS, data=json.dumps(request_data), verify=self.gs_verify_ssl)
        if response.status_code == 200:
            if return_json and response.json().get('status') == 0:
                return response.json()['response']
            else:
                return response.content

    def gs_get_cookie(self):
        def get_challenge():
            challenge_url = '{}/api'.format(self.gs_api_url)
            data = {
                'request': {
                    'action': 'challenge',
                    'user': self.gs_api_user,
                    'version': self.gs_api_version
                }
            }    
            response = requests.post(
                challenge_url, headers=GS_HEADERS, data=json.dumps(data), verify=self.gs_verify_ssl)
            if response.status_code == 200:
                return response.json().get('response').get('challenge')            
            else:
                raise Exception('Failed to get challenge')
            
        def login(challenge):
            login_url = '{}/api'.format(self.gs_api_url)
            headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'Connection': 'close'
            }
            # Calculate the password hash            
            token = hashlib.md5((challenge + self.gs_api_password).encode('utf-8')).hexdigest()
            data = {
                'request': {
                    'action': 'login',
                    'token': token,
                    'user': self.gs_api_user
                }
            }    
            response = requests.post(
                login_url, headers=GS_HEADERS, data=json.dumps(data), verify=self.gs_verify_ssl)
            if response.status_code == 200 and response.json().get('status') == 0:
                cookie = response.json().get('response').get('cookie')
                self.write({
                    'gs_cookie': cookie,
                    # 10 minutes expiration as defined by GS API.
                    'gs_cookie_expire_time': datetime.now() + timedelta(seconds=600)
                })
                debug(self, 'GS: Got a new access cookie.')                                
                return cookie
            else:
                raise Exception('Failed to login')
        # Get challenge and login and return the cookie
        return login(get_challenge())


    def get_system_information(self):        
        data = self.gs_api_request('getSystemStatus')
        data.update(self.gs_api_request('getSystemGeneralStatus'))
        self.write({
            'gs_model_name': data['product-model'],
            'gs_system_time': data['system-time'],
            'gs_uptime': data['up-time']
        })

    def gs_sync_users(self):
        # Create PBX users from extensions.
        created_extensions = []
        res = self.gs_api_request('listAccount')
        data = self.gs_api_request('listAccount')['account']
        for rec in data:
            existing_user = self.env['asterisk_plus.user'].search([('exten', '=', rec['extension'])])
            if not existing_user:
                # Extension does not exist, create one
                user = self.env['asterisk_plus.user'].create({'exten': rec['extension']})
                self.env['asterisk_plus.user_channel'].create({
                    'asterisk_user': user.id,
                    'sip_transport': 'udp-user',
                    'originate_context': 'from-internal',
                    'name': 'PJSIP/{}'.format(user.exten)
                })
                debug(self, 'Created PBX user for gs extension %s' % rec['extension'])
                created_extensions.append(rec['extension'])
            else:
                debug(self, 'Omitting existing PBX user %s for GS exten %s' % (
                    existing_user.name, rec['extension']))
        if created_extensions:
            self.env['asterisk_plus.settings'].odoopbx_notify(
                title="PBX users", message='Created ' + ', '.join(created_extensions))
        else:
            self.env['asterisk_plus.settings'].odoopbx_notify(
                title="PBX users", message='No new PBX users created.')


    @api.model
    def gs_set_default_webrtc(self):
        server = self.env.ref('asterisk_plus.default_server')
        server.sip_peer_transport = 'webrtc-user'
        # Set transport for all users if any
        self.env['asterisk_plus.user_channel'].write({'sip_transport': 'webrtc-user'})
