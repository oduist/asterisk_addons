# -*- coding: utf-8 -*

from datetime import datetime, timedelta
import requests
from requests.compat import urljoin
from urllib.parse import urlencode
from odoo import fields, models
from odoo.exceptions import ValidationError
from odoo.addons.asterisk_plus.models.settings import debug


class YeastarSettings(models.Model):
    _inherit = 'asterisk_plus.server'

    yeastar_api_url = fields.Char()
    yeastar_api_client_id = fields.Char()
    yeastar_api_client_secret = fields.Char()
    yeastar_access_token_expire_time = fields.Datetime()
    yeastar_access_token = fields.Char()
    yeastar_refresh_token_expire_time = fields.Datetime()
    yeastar_refresh_token = fields.Char()
    yeastar_model = fields.Selection([
        ('p_se', 'P-series Software Edition'),
        ('s', 'S-series'),
    ])
    yeastar_api_version = fields.Selection([
        ('api/v1.1.0', 'v1.1.0 (S)'),
        ('openapi/v1.0', 'v1.0 (P SE)')
    ])
    yeastar_verify_ssl = fields.Boolean(default=True)
    yeastar_model_name = fields.Char(readonly=True)
    yeastar_system_time = fields.Char(readonly=True)
    yeastar_uptime = fields.Char(readonly=True)

    def yeastar_api_request(self, path, method='post', data={},
            refresh_token=False, refresh_count=0, return_json=True):
        return getattr(self, 'yeastar_{}_api_request'.format(self.yeastar_model))(
            path, method=method, data=data, refresh_token=refresh_token,
            refresh_count=refresh_count, return_json=return_json)

    def yeastar_s_api_request(self, path, method='post', data={},
            refresh_token=False, refresh_count=0, return_json=True):
        # Set refresh count in order to protect from recursion
        self.ensure_one()
        # Check for cached token
        if not refresh_token and self.yeastar_access_token_expire_time:
            expire_seconds = (self.yeastar_access_token_expire_time - datetime.now()).seconds
            if expire_seconds > 60:
                debug(self, 'Yeastar: using cached access token.')
                access_token = self.yeastar_access_token
            else:
                access_token = self.yeastar_s_get_access_token()
                refresh_count += 1
        else:
            access_token = self.yeastar_s_get_access_token()
            refresh_count += 1
        url = urljoin(self.yeastar_api_url, '{}/{}'.format(self.yeastar_api_version, path))
        if method == 'get':
            data.update({
                'token': access_token
            })
            query_string = urlencode(data)
            url = '{}?{}'.format(url, query_string)
            resp = requests.get(url, verify=self.yeastar_verify_ssl)
        else:
            url = '{}?token={}'.format(url, access_token)
            resp = requests.post(url, json=data, verify=self.yeastar_verify_ssl)
        resp.raise_for_status()
        if return_json:
            res = resp.json()
            if res.get('status') == 'Failed' and res.get('errno') == '20004':
                # Access token expires, repeat request with new token.
                return self.yeastar_s_api_request(path, method=method, data=data,
                    refresh_token=True, refresh_count=refresh_count, return_json=return_json)

            return resp.json()
        else:
            return resp


    def yeastar_p_se_api_request(self, path, method='post', data={},
            refresh_token=False, refresh_count=0, return_json=True):
        # Set refresh count in order to protect from recursion
        self.ensure_one()
        # Check for cached token
        if not refresh_token and self.yeastar_access_token_expire_time:
            expire_seconds = (self.yeastar_access_token_expire_time - datetime.now()).seconds
            if expire_seconds > 60:
                debug(self, 'Yeastar: using cached access token.')
                access_token = self.yeastar_access_token
            else:
                access_token = self.yeastar_get_access_token()
                refresh_count += 1
        else:
            access_token = self.yeastar_get_access_token()
            refresh_count += 1
        url = urljoin(self.yeastar_api_url, '{}/{}'.format(self.yeastar_api_version, path))
        if method == 'get':
            data.update({
                'access_token': access_token
            })
            query_string = urlencode(data)
            url = '{}?{}'.format(url, query_string)
            resp = requests.get(url, verify=self.yeastar_verify_ssl)
        else:
            url = '{}?access_token={}'.format(url, access_token)
            resp = requests.post(url, json=data, verify=self.yeastar_verify_ssl)
        resp.raise_for_status()
        result = resp.json()
        if result.get('errmsg') == 'TOKEN EXPIRED' and refresh_count < 2:
            return self.yeastar_p_se_api_request(
                path, method=method, data=data, refresh_token=True, refresh_count=refresh_count)
        if result.get('errmsg') != 'SUCCESS':
            raise Exception('{}: {}'.format(result['errmsg'], result))
        return result

    def yeastar_p_se_get_access_token(self):
        url = urljoin(self.yeastar_api_url, '{}/get_token'.format(self.yeastar_api_version))
        response = requests.post(url, verify=self.yeastar_verify_ssl, json=
            {'username': self.yeastar_api_client_id,
             'password': self.yeastar_api_client_secret})
        response.raise_for_status()
        data = response.json()
        if data.get('errmsg') != 'SUCCESS':
            raise Exception('{}: {}'.format(data['errmsg'], data))
        access_token = data['access_token']
        self.write({
            'yeastar_access_token': access_token,
            'yeastar_access_token_expire_time': datetime.now() + timedelta(
                seconds=data['access_token_expire_time']),
            'yeastar_refresh_token': data['refresh_token'],
            'yeastar_refresh_token_expire_time': datetime.now() + timedelta(
                seconds=data['refresh_token_expire_time'])
        })
        debug(self, 'Yeastar: Got a new access token.')
        return access_token

    def yeastar_s_get_access_token(self):
        url = urljoin(self.yeastar_api_url, '{}/login'.format(self.yeastar_api_version))
        import hashlib
        response = requests.post(url, verify=self.yeastar_verify_ssl, json=
            {'username': self.yeastar_api_client_id,
             'password': hashlib.md5(self.yeastar_api_client_secret.encode()).hexdigest()})
        response.raise_for_status()
        data = response.json()
        access_token = data['token']
        self.write({
            'yeastar_access_token': access_token,
            'yeastar_access_token_expire_time': datetime.now() + timedelta(minutes=30)
        })
        debug(self, 'Got a new Yeastar access token.')
        return access_token

    def get_system_information(self):
        getattr(self, 'yeastar_{}_get_system_information'.format(self.yeastar_model))()

    def yeastar_s_get_system_information(self):
        data = self.yeastar_s_api_request('deviceinfo/query', method='get')
        print(data)
        self.write({
            'yeastar_model_name': data['deviceinfo']['devicename'],
            'yeastar_system_time': data['deviceinfo']['systemtime'],
            'yeastar_uptime': data['deviceinfo']['uptime']
        })
        return

    def yeastar_p_se_get_system_information(self):
        data = self.yeastar_p_se_api_request('system/information', method='get')['data']
        self.write({
            'yeastar_model_name': data['model_name'],
            'yeastar_system_time': data['system_time'],
            'yeastar_uptime': str(timedelta(seconds=data['up_time']))
        })

    def yeastar_sync_users(self):
        getattr(self, 'yeastar_{}_sync_users'.format(self.yeastar_model))()

    def yeastar_p_se_sync_users(self):
        # Create PBX users from extensions.
        created_extensions = []
        data = self.yeastar_p_se_api_request('extension/list', method='get')
        for rec in data['data']:
            existing_user = self.env['asterisk_plus.user'].search([('exten', '=', rec['number'])])
            if not existing_user:
                # Extension does not exist, create one
                user = self.env['asterisk_plus.user'].create({'exten': rec['number']})
                self.env['asterisk_plus.user_channel'].create({
                    'asterisk_user': user.id,
                    'sip_transport': 'udp-user',
                    'originate_context': 'DLPN_DialPlan{}'.format(user.exten),
                    'name': 'PJSIP/{}'.format(user.exten)
                })
                debug(self, 'Created PBX user for Yeastar extension %s' % rec['number'])
                created_extensions.append(rec['number'])
            else:
                debug(self, 'Omitting existing PBX user %s for Yeastar exten %s' % (
                    existing_user.name, rec['number']))
        if created_extensions:
            self.env['asterisk_plus.settings'].asterisk_plus_notify(
                title="PBX users", message='Created ' + ', '.join(created_extensions))
        else:
            self.env['asterisk_plus.settings'].asterisk_plus_notify(
                title="PBX users", message='No new PBX users created.')

    def yeastar_s_sync_users(self):
        # Create PBX users from extensions.
        created_extensions = []
        data = self.yeastar_s_api_request('extensionlist/query', method='get')
        for rec in [k for k in data['extlist'] if k['type'] == 'SIP']:
            existing_user = self.env['asterisk_plus.user'].search([('exten', '=', rec['extnumber'])])
            if not existing_user:
                # Extension does not exist, create one
                user = self.env['asterisk_plus.user'].create({'exten': rec['extnumber']})
                self.env['asterisk_plus.user_channel'].create({
                    'asterisk_user': user.id,
                    'sip_transport': 'udp-user',
                    'originate_context': 'DLPN_DialPlan{}'.format(user.exten),
                    'name': 'PJSIP/{}'.format(user.exten)
                })
                debug(self, 'Created PBX user for Yeastar extension %s' % rec['extnumber'])
                created_extensions.append(rec['extnumber'])
            else:
                debug(self, 'Omitting existing PBX user %s for Yeastar exten %s' % (
                    existing_user.name, rec['extnumber']))
        if created_extensions:
            self.env['asterisk_plus.settings'].asterisk_plus_notify(
                title="PBX users", message='Created ' + ', '.join(created_extensions))
        else:
            self.env['asterisk_plus.settings'].asterisk_plus_notify(
                title="PBX users", message='No new PBX users created.')
