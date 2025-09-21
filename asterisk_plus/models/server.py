# -*- coding: utf-8 -*-
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2023
import base64
from datetime import datetime
import json
import logging
import requests
import time
import unicodedata
import urllib
import urllib3
import sys
if sys.version_info[0] > 2:
    from urllib.parse import urljoin
else:
    from urlparse import urljoin
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import uuid
from odoo import api, models, fields, SUPERUSER_ID, registry, release, tools, release, _
from odoo.exceptions import ValidationError, UserError
from .settings import debug
from .res_partner import strip_number, format_number


logger = logging.getLogger(__name__)

DEFAULT_SIP_TEMPLATES="""
[trunk_defaults](!)
type = wizard
transport = transport-udp
endpoint/allow_subscribe = no
endpoint/allow = !all,ulaw,alaw
aor/qualify_frequency = 30
registration/expiration = 1800
endpoint/inband_progress = yes

[webrtc-user](!)
type = wizard
transport = transport-wss
accepts_registrations = yes
sends_registrations = no
accepts_auth = yes
sends_auth = no
endpoint/webrtc = yes
endpoint/dtls_auto_generate_cert = yes
endpoint/context = from-internal
endpoint/allow = !all,g722,alaw,ulaw
endpoint/direct_media = no
endpoint/force_rport = yes
endpoint/rewrite_contact = yes
endpoint/rtp_symmetric = yes
endpoint/allow_transfer = yes
endpoint/send_diversion = yes
endpoint/ice_support = yes
aor/qualify_frequency = 30
aor/authenticate_qualify = no
aor/max_contacts = 5
aor/remove_existing = yes
aor/minimum_expiration = 30
aor/support_path = yes
endpoint/inband_progress = yes

[udp-user](!)
type = wizard
endpoint/rtp_symmetric=yes
transport = transport-udp
accepts_registrations = yes
sends_registrations = no
accepts_auth = yes
sends_auth = no
endpoint/context = from-internal
endpoint/allow_subscribe = yes
endpoint/allow = !all,ulaw,gsm,alaw
endpoint/direct_media = no
endpoint/force_rport = yes
endpoint/ice_support = yes
endpoint/moh_suggest = default
endpoint/send_rpid = yes
endpoint/rewrite_contact = yes
endpoint/send_pai = yes
endpoint/allow_transfer = yes
endpoint/trust_id_inbound = yes
endpoint/device_state_busy_at = 1
endpoint/trust_id_outbound = yes
endpoint/send_diversion = yes
aor/qualify_frequency = 30
aor/authenticate_qualify = no
aor/max_contacts = 1
aor/remove_existing = yes
aor/minimum_expiration = 30
aor/support_path = yes

[tcp-user](!)
type = wizard
endpoint/rtp_symmetric=yes
transport = transport-tcp
accepts_registrations = yes
sends_registrations = no
accepts_auth = yes
sends_auth = no
endpoint/context = from-internal
endpoint/allow_subscribe = yes
endpoint/allow = !all,ulaw,gsm,alaw
endpoint/direct_media = no
endpoint/force_rport = yes
endpoint/ice_support = yes
endpoint/moh_suggest = default
endpoint/send_rpid = yes
endpoint/rewrite_contact = yes
endpoint/send_pai = yes
endpoint/allow_transfer = yes
endpoint/trust_id_inbound = yes
endpoint/device_state_busy_at = 1
endpoint/trust_id_outbound = yes
endpoint/send_diversion = yes
aor/qualify_frequency = 30
aor/authenticate_qualify = no
aor/max_contacts = 1
aor/remove_existing = yes
aor/minimum_expiration = 30
aor/support_path = yes
"""

DEFAULT_SIP_TEMPLATE="""[{username}]({template})
inbound_auth/username = {username}
inbound_auth/password = {password}
endpoint/callerid = {callerid}
hint_exten = {exten}
"""

SIP_TRANSPORT_SELECTION =[
    ('webrtc-user', 'WebRTC'),
    ('udp-user', 'UDP'),
    ('tcp-user', 'TCP')
]

def get_default_server(rec):
    try:
        return rec.env.ref('asterisk_plus.default_server')
    except Exception:
        logger.exception('Cannot get default server!')
        return False


class AgentOptions(models.Model):
    _name = 'asterisk_plus.agent_options'
    _description = 'Agent Options'
    _order = 'key'

    server = fields.Many2one('asterisk_plus.server', required=True, ondelete='cascade')
    key = fields.Char(required=True)
    value = fields.Char(required=True)


class Server(models.Model):
    _name = 'asterisk_plus.server'
    _description = "Asterisk Server"

    name = fields.Char(required=True)
    is_module_update = fields.Boolean()
    market_download_link = fields.Html(compute='_get_market_download_link')
    is_check_new_enabled = fields.Boolean(default=True)
    user = fields.Many2one('res.users', ondelete='restrict', required=True, readonly=True)
    tz = fields.Selection(related='user.tz', readonly=False)
    country_id = fields.Many2one(related='user.country_id', readonly=False)
    agent_initialized = fields.Boolean()
    permit_agent_initialization = fields.Boolean(string='Permit Initialization', default=True)
    auto_create_pbx_users = fields.Boolean(string="Autocreate PBX Users",
        help="Automatically generate PBX users for Odoo users")
    generate_sip_peers = fields.Boolean(string='Generate SIP peers',
        help="""Enable get_sip_conf controller.
        It generates part of Asterisk SIP config file according to SIP Conf Template
        for each channel of every PBX User.""")
    sip_peer_transport = fields.Selection(string='SIP template name',
        selection=SIP_TRANSPORT_SELECTION,
        help='Configuration template name which is applied to the peer by default, e.g. [name](template)',
        required=True, default='udp-user')
    sip_peer_template = fields.Text(
        string="SIP Peer Template",
        help="SIP configuration template for PBX users",
        default=DEFAULT_SIP_TEMPLATE)
    sip_templates = fields.Text(string='SIP Templates', required=True, default=DEFAULT_SIP_TEMPLATES)
    security_token = fields.Char(required=False, default=lambda x: uuid.uuid4())
    sip_protocol = fields.Selection(string='SIP protocol',
        selection=[('SIP', 'SIP'), ('PJSIP', 'PJSIP')], default='PJSIP', required=True)
    sip_peer_start_exten = fields.Char('Starting Exten', default='201')
    # Agent options
    ami_host = fields.Char('AMI Host', required=True, default='localhost')
    ami_port = fields.Integer('AMI Port', required=True, default=5038)
    ami_user = fields.Char('AMI User', required=True, default='asterisk_plus_agent')
    ami_password = fields.Char('AMI Password', default=lambda x: str(uuid.uuid4()), required=True)
    ami_trace = fields.Boolean('AMI Trace')

    agent_options = fields.One2many('asterisk_plus.agent_options', 'server')

    _sql_constraints = [
        ('user_unique', 'UNIQUE("user")', 'This user is already used for another server!'),
    ]

    def write(self, vals):
        res = super().write(vals)
        autocreate_enabled =  vals.get('auto_create_pbx_users', False)
        if autocreate_enabled:
            self.run_auto_create_pbx_users()
        return res

    @api.constrains('agent_initialized')
    def _check_permit_initialization(self):
        for rec in self:
            if not rec.agent_initialized and not rec.permit_agent_initialization:
                raise ValidationError('Permit Agent initialization first!')

    @api.model
    def run_auto_create_pbx_users(self):
        debug(self, 'Run autocreate PBX users')
        users = self.env['res.users'].search([]).filtered(
            lambda x: x.has_group('asterisk_plus.group_asterisk_user'))
        self.env['asterisk_plus.user'].auto_create(users)

    def get_sip_peers(self):
        if not self.generate_sip_peers:
            logger.info('SIP peers generation is not enabled.')
            return False

        sip_content = '{}\n'.format(self.sip_templates)
        for channel in self.env['asterisk_plus.user_channel'].sudo().search(
                [('server', '=', self.id)]):
            if not channel.sip_password:
                logger.info('SIP channel %s has not password, not including.', channel.name)
                continue
            user_name = unicodedata.normalize('NFKD', channel.user.name).encode('ASCII', 'ignore').decode('ASCII')
            sip_content += self.sip_peer_template.format(
                template=channel.sip_transport,
                password=channel.sip_password,
                username=channel.sip_user,
                exten=channel.asterisk_user.exten,
                callerid='{} <{}>'.format(user_name, channel.asterisk_user.callerid_number)
            )
            sip_content += '\n\n'
        return sip_content

    def _get_market_download_link(self):
        for rec in self:
            rec.market_download_link = '<a href="https://apps.odoo.com/apps/{}/asterisk_plus" target="_blank">Download new version of Asterisk Plus app.</a>'.format(
                release.major_version)

    def open_server_form(self):
        rec = self.env.ref('asterisk_plus.default_server')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'asterisk_plus.server',
            'res_id': rec.id,
            'name': 'Agent',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
        }

    def local_job(self, fun, args=None, kwargs={}, timeout=6,
                  res_model=None, res_method=None, res_notify_uid=None,
                  res_notify_title='PBX', pass_back=None,
                  raise_exc=True):
        self.ensure_one()
        res = {}
        response = None
        # debug(self, 'Server job, args: {}, kwargs: {}, res: {}.{}, pass_back: {}'.format(
        #    args, kwargs, res_model, res_method, pass_back))
        try:
            settings = self.env['asterisk_plus.settings'].sudo()
            if not settings.get_param('is_subscribed'):
                raise ValidationError('Asterisk Plus has no subscription!')
            api_key = settings.get_param('api_key')
            api_url = settings.get_param('api_url')
            instance_uid = settings.get_param('instance_uid')
            data = {
                'fun': fun, 'args': args, 'kwargs': kwargs,
                'res_model': res_model, 'res_method': res_method,
                'res_notify_uid': res_notify_uid,
                'res_notify_title': res_notify_title, 'pass_back': pass_back,
            }
            # debug(self, 'Sending API call to: %s' % api_url)
            response = requests.post(
                urljoin(api_url, 'app/asterisk_plus/agent'),
                headers={
                    'x-api-key': api_key,
                    'x-instance-uid': instance_uid,
                }, json=data, timeout=timeout, verify=False)
            response.raise_for_status()
            # debug(self, 'API response: %s' % response.text)
            return response
        except Exception as e:
            if raise_exc:
                if response is None:
                    raise ValidationError(str(e))
                else:
                    raise ValidationError(response.text)
            else:
                logger.exception('Local job error:')

    def ping_agent(self):
        self.ensure_one()
        try:
            self.local_job(fun='test.ping', res_notify_uid=self.env.user.id,
                res_notify_title='Async', timeout=5)
        except Exception as e:
            raise ValidationError(str(e))

    def reload_config(self):
        self.ensure_one()
        try:
            self.local_job(fun='agent.reload_config', res_notify_uid=self.env.user.id,
                res_notify_title='Reload Config', timeout=5)
        except Exception as e:
            raise ValidationError(str(e))

    def ami_action(self, action, timeout=5, no_wait=False, as_list=None, **kwargs):
        return self.local_job(
            fun='asterisk.manager_action',
            args=action,
            kwargs={
                'as_list': as_list
            }, **kwargs)

    def asterisk_ping(self):
        """Called from server form to test AMI connectivity.
        """
        try:
            self.ami_action({'Action': 'Ping'}, res_notify_uid=self.env.user.id)
        except Exception as e:
            raise ValidationError(str(e))

    @api.model
    def originate_call(self, number, model=None, res_id=None, user=None, dtmf_variables=None):
        """Originate Call with click2dial widget.

          Args:
            number (str): Number to dial.
        """
        # Strip spaces and dash.
        number = number.replace(' ', '')
        number = number.replace('-', '')
        number = number.replace('(', '')
        number = number.replace(')', '')
        debug(self, '{} {} {} {}'.format(number, model, res_id, user))
        if not user:
            user = self.env.user
        if not user.asterisk_users:
            raise ValidationError('PBX User is not defined!') # sdd sd sd sd sdsd sdsd s
        # Format number
        if model and res_id:
            obj = self.env[model].browse(res_id)
            if obj and getattr(obj, '_get_country', False):
                country = obj._get_country()
                number = format_number(self, number, country)
        # Set CallerIDName
        if model and model != 'asterisk_plus.call' and res_id:
            obj = self.env[model].browse(res_id)
            if hasattr(obj, 'name'):
                callerid_name = 'To: {}'.format(obj.name)
        else:
            callerid_name = ''
        # Get originate timeout
        originate_timeout = float(self.env[
            'asterisk_plus.settings'].sudo().get_param('originate_timeout'))

        for asterisk_user in self.env.user.asterisk_users:
            if not asterisk_user.channels:
                raise ValidationError('SIP channels not defined for user!')
            originate_channels = [k for k in asterisk_user.channels if k.originate_enabled]
            if not originate_channels:
                raise ValidationError('No channels with originate enabled!')
            variables = asterisk_user._get_originate_vars()
            for ch in originate_channels:
                channel_vars = variables.copy()
                if ch.auto_answer_header:
                    header = ch.auto_answer_header
                    try:
                        pos = header.find(':')
                        param = header[:pos]
                        val = header[pos+1:]
                        if 'PJSIP' in ch.name.upper():
                            channel_vars.append(
                                'PJSIP_HEADER(add,{})={}'.format(
                                    param.lstrip(), val.lstrip()))
                        else:
                            channel_vars.append(
                                'SIPADDHEADER={}: {}'.format(
                                    param.lstrip(), val.lstrip()))
                    except Exception:
                        logger.warning(
                            'Cannot parse auto answer header: %s', header)

                if dtmf_variables:
                    channel_vars.extend(dtmf_variables)

                channel_id = str(uuid.uuid4())
                other_channel_id = str(uuid.uuid4())
                # Create a call.
                call_data = {
                    'server': asterisk_user.server.id,
                    'uniqueid': channel_id,
                    'calling_user': self.env.user.id,
                    'calling_number': asterisk_user.exten,
                    'called_number': number,
                    'started': datetime.now(),
                    'direction': 'out',
                    'is_active': True,
                    'status': 'progress',
                    'model': model,
                    'res_id': res_id,
                }
                if model == 'res.partner':
                    # Set call partner
                    call_data['partner'] = res_id
                call = self.env['asterisk_plus.call'].create(call_data)
                self.env['asterisk_plus.channel'].create({
                        'server': asterisk_user.server.id,
                        'user': self.env.user.id,
                        'call': call.id,
                        'channel': ch.name,
                        'uniqueid': channel_id,
                        'linkedid': other_channel_id,
                        'is_active': True,
                })
                if not self.env.context.get('no_commit'):
                    self.env.cr.commit()
                action = {
                    'Action': 'Originate',
                    'Context': ch.originate_context,
                    'Priority': '1',
                    'Timeout': 1000 * originate_timeout,
                    'Channel': ch.name,
                    'Exten': number,
                    'Async': 'true',
                    'EarlyMedia': 'true',
                    'CallerID': '{} <{}>'.format(callerid_name, number),
                    'ChannelId': channel_id,
                    'OtherChannelId': other_channel_id,
                    'Variable': channel_vars,
                }
                ch.server.ami_action(action, res_model='asterisk_plus.server',
                                     res_method='originate_call_response',
                                     pass_back={'notify_uid': self.env.user.id,
                                                'channel_id': channel_id})

    @api.model
    def originate_call_response(self, data, channel_id=None, notify_uid=None):
        def _check_error_response(data):
            if data['Response'] == 'Error':
                logger.info('Originate error: %s', data['Message'])
                # Hangup channel.
                call = self.env['asterisk_plus.call'].search(
                    [('uniqueid', '=', channel_id)])
                call.write({'status': 'failed', 'is_active': False})
                call.channels.write({'is_active': False})
                self.env['asterisk_plus.settings'].odoopbx_notify(
                    'Call to {} failed: {}'.format(
                        call.called_number, data['Message']),
                    notify_uid=notify_uid,
                    warning=True)
                return True
        if isinstance(data, dict):
            _check_error_response(data)
        elif isinstance(data, list):
            # Multiple reply, action result and also AMI event with OriginateReply.
            for event in data:
                _check_error_response(event)
                self.env['asterisk_plus.channel'].on_ami_originate_response_failure(event)
        return True

    def reload_action(self, module=None, notify_uid=None, delay=1):
        self.ensure_one()
        action = {'Action': 'Reload'}
        if module:
            action['Module'] = module
        self.ami_action(
            action,
            timeout=delay,
            res_notify_uid=notify_uid or self.env.uid)

    def get_system_information(self):
        self.ensure_one()
        action = {'Action': 'CoreStatus'}
        self.ami_action(action, res_notify_uid=self.env.uid)

    @api.model
    def generate_voicemail_conf(self):
        # This returns a snippet to be included from Asterisk voicemail.conf.
        res = []
        # Iterate over PBX users.
        pbx_users = self.env['asterisk_plus.user'].search([])
        for user in pbx_users:
            res.append('{} => 36463737351,{},{}'.format(user.exten, user.user.name,user.user.email))
        return '\n'.join(res)

    @api.constrains('sip_templates')
    def _check_template_names(self):
        for rec in self:
            if not all(['[udp-user]' in rec.sip_templates,
                    '[tcp-user]' in rec.sip_templates, '[webrtc-user]' in rec.sip_templates]):
                raise ValidationError('Template must contains [udp-user], [tcp-user], [webrtc-user]!')
