# -*- coding: utf-8 -*-

from datetime import datetime
import inspect
import json
import requests
import logging
import re
from urllib.parse import urljoin
import uuid
from odoo import fields, models, api, tools, release, release
from odoo.exceptions import ValidationError, UserError
from odoo.tools import ormcache

logger = logging.getLogger(__name__)

MODULE_NAME = 'asterisk_plus'
MAX_EXTEN_LEN = 6
FORMAT_TYPE = 'e164'
RECORDING_ACCESS_SELECTION = [
    ('local', 'Local Download'),
]

PREPAID_PAYMENT_URL = 'https://buy.stripe.com/aEU01VaER5D15lC4gj'
# Starting from Odoo 12.0 there is admin user with ID 2.
ADMIN_USER_ID = 1 if release.version_info[0] <= 11 else 2


def debug(rec, message, level='info'):
    caller_module = inspect.stack()[1][3]
    if level == 'info':
        fun = logger.info
    elif level == 'warning':
        fun = logger.warning
        fun('++++++ {}: {}'.format(caller_module, message))
    elif level == 'error':
        fun = logger.error
        fun('++++++ {}: {}'.format(caller_module, message))
    if rec.env['asterisk_plus.settings'].sudo().get_param('debug_mode'):
        rec.env['asterisk_plus.debug'].sudo().create({
            'model': str(rec),
            'message': caller_module + ': ' + message,
        })
        if level == 'info':
            fun('++++++ {}: {}'.format(caller_module, message))


def strip_number(number):
    """Strip number formating"""
    pattern = r'[\s\(\)\-\+]'
    return re.sub(pattern, '', number).lstrip('0')


class TranscriptionRules(models.Model):
    _name = 'asterisk_plus.transcription_rule'
    _description = 'Transcription rule'
    _order = 'id'

    settings = fields.Many2one('asterisk_plus.settings', required=True, default=1)
    calling_number = fields.Char(required=True)
    called_number = fields.Char(required=True)

    @api.model
    def check_rules(self, calling_number, called_number):
        for rec in self.search([]):
            try:
                if calling_number and not re.search(rec.calling_number, calling_number):
                    debug(self, 'Transcription rule {} calling number pattern does not match'.format(rec.id))
                    continue
                if called_number and not re.search(rec.called_number, called_number):
                    debug(self, 'Transcription rule {} called number pattern does not match'.format(rec.id))
                    continue
                debug(self, 'Transcription rule {} matched!'.format(rec.id))
                return True
            except Exception as e:
                logger.error('Error checking transcription rule %s: %s', rec.id, e)

class Settings(models.Model):
    """One record model to keep all settings. The record is created on
    get_param / set_param methods on 1-st call.
    """
    _name = 'asterisk_plus.settings'
    _description = 'Settings'

    #: Just a friends name for a settings form.
    name = fields.Char(compute='_get_name')
    #: Debug mode
    debug_mode = fields.Boolean()
    #: Save all AMI messages on channels
    permit_ip_addresses = fields.Char(
        string='Permit IP address(es)',
        help='Comma separated list of IP addresses permitted to query caller '
             'ID number, etc. Leave empty to allow all addresses.')
    originate_context = fields.Char(
        string='Default context',
        default='from-internal', required=True,
        help='Default context to set when creating PBX / Odoo user mapping.')
    originate_timeout = fields.Integer(default=60, required=True)
    # Search numbers by exact or partial match
    number_search_operation = fields.Selection(
        [('=', 'Equal'), ('like', 'Like')],
        default='=', required=True)
    disable_phone_format = fields.Boolean(help='Disable phone number format, e.g. +123456789 => +1 234 56 78')
    # Recording settings
    recordings_access = fields.Selection(
        selection=RECORDING_ACCESS_SELECTION, required=True, default='local')
    recordings_access_url = fields.Char(
        string='Access URL', default='http://localhost:8088/static/monitor/')
    recordings_s3_bucket = fields.Char(string='S3 Bucket')
    recordings_s3_key = fields.Char(string='S3 Key')
    recordings_s3_secret = fields.Char(string='S3 Secret')
    recordings_s3_region = fields.Char('S3 Region')
    record_calls = fields.Boolean(
        default=True,
        help="If checked, call recording will be enabled")
    recording_storage = fields.Selection(
        [('db', 'Database'), ('filestore', 'Files')],
        default='filestore', required=True)
    use_mp3_encoder = fields.Boolean(
        default=True, string="Encode to mp3",
        help="If checked, call recordings will be encoded using MP3")
    mp3_encoder_bitrate = fields.Selection(
        selection=[('16', '16 kbps'),
                   ('32', '32 kbps'),
                   ('48', '48 kbps'),
                   ('64', '64 kbps'),
                   ('96', '96 kbps'),
                   ('128', '128 kbps')],
        default='64',
        required=False)
    mp3_encoder_quality = fields.Selection(
        selection=[('2', '2-Highest'),
                   ('3', '3'),
                   ('4', '4'),
                   ('5', '5'),
                   ('6', '6'),
                   ('7', '7-Fastest')],
        default='4',
        required=False)
    calls_keep_days = fields.Char(
        string='Call History Keep Days',
        default='365',
        required=True,
        help='Calls older then set value will be removed.')
    recordings_keep_days = fields.Char(
        string='Call Recording Keep Days',
        default='365',
        required=True,
        help='Call recordings older then set value will be removed.')
    auto_reload_calls = fields.Boolean(
        default=True,
        help='Automatically refresh active calls view')
    auto_reload_channels = fields.Boolean(
        help='Automatically refresh active channels view')
    auto_create_partners = fields.Boolean(
        default=False,
        help='Automatically create partner record on calls from uknown numbers.')
    ############# TRANSCRIPT FIELDS ##############################################
    transcribe_calls = fields.Boolean()
    openai_api_key = fields.Char(groups="asterisk_plus.group_asterisk_admin")
    openai_api_key_display = fields.Char(string='OpenAI API Key', groups="asterisk_plus.group_asterisk_admin")
    transcription_rules = fields.One2many('asterisk_plus.transcription_rule', 'settings')
    summary_prompt = fields.Text(required=True, default='Summarise this phone call')
    completion_model = fields.Char(required=True, default='gpt-4o')
    register_summary = fields.Boolean(help='Register summary at partner of reference chat.', default=True)
    remove_recording_after_transcript = fields.Boolean()
    #############  REGISTRATION FIELDS   ###############################################
    instance_uid = fields.Char('Instance UID', compute='_get_instance_data')
    api_url = fields.Char('API URL', compute='_get_instance_data')
    api_fallback_url = fields.Char('API Fallback URL', compute='_get_instance_data')
    # Registration fields
    customer_code = fields.Char()
    registration_number = fields.Char(compute='_get_instance_data')
    registration_key = fields.Char('API Key', compute='_get_instance_data')
    is_registered = fields.Boolean()
    i_agree_to_register = fields.Boolean()
    i_agree_to_contact = fields.Boolean()
    i_agree_to_receive = fields.Boolean()
    installation_date = fields.Datetime(compute='_get_instance_data')
    module_version = fields.Char(compute='_get_instance_data')
    odoo_version = fields.Char(compute='_get_instance_data')
    admin_name = fields.Char(compute='_get_instance_data')
    admin_phone = fields.Char(compute='_get_instance_data')
    admin_email = fields.Char(compute='_get_instance_data')
    company_name = fields.Char(compute='_get_instance_data')
    company_email = fields.Char(compute='_get_instance_data')
    company_phone = fields.Char(compute='_get_instance_data')
    company_country = fields.Char(compute='_get_instance_data')
    company_state_name = fields.Char(compute='_get_instance_data')
    company_country_code = fields.Char(compute='_get_instance_data')
    company_country_name = fields.Char(compute='_get_instance_data')
    company_city = fields.Char(compute='_get_instance_data')
    web_base_url = fields.Char(compute='_get_instance_data', string='Odoo URL')

    def _get_instance_data(self):
        module = self.env['ir.module.module'].sudo().search([('name', '=', 'asterisk_plus')])
        for rec in self:
            rec.module_version = re.sub(r'^(\d+\.\d+\.)', '', module.installed_version)
            rec.odoo_version = release.major_version
            # Generate instance UUID.
            instance_uid = self.env['ir.config_parameter'].sudo().get_param('asterisk_plus.instance_uid')
            if not instance_uid:
                instance_uid = str(uuid.uuid4())
                self.env['ir.config_parameter'].set_param('asterisk_plus.instance_uid', instance_uid)
            rec.instance_uid = instance_uid
            rec.installation_date = self.env['ir.config_parameter'].sudo().get_param('asterisk_plus.installation_date')
            rec.api_url = self.env['ir.config_parameter'].sudo().get_param('asterisk_plus.api_url')
            rec.api_fallback_url = self.env['ir.config_parameter'].sudo().get_param('asterisk_plus.api_fallback_url')
            rec.registration_key = self.env['ir.config_parameter'].sudo().get_param('asterisk_plus.registration_key')
            rec.company_email = self.env.user.company_id.email
            rec.company_name = self.env.user.company_id.name
            rec.company_phone = self.env.user.company_id.phone
            rec.company_country = self.env.user.company_id.country_id.name
            rec.company_city = self.env.user.company_id.city
            rec.company_country_code = self.env.user.company_id.country_id.code
            rec.company_country_name = self.env.user.company_id.country_id.name
            rec.company_state_name = self.env.user.company_id.partner_id.state_id.name
            rec.admin_name = self.env['res.users'].browse(ADMIN_USER_ID).partner_id.name
            rec.admin_email = self.env['res.users'].browse(ADMIN_USER_ID).partner_id.email
            rec.admin_phone = self.env['res.users'].browse(ADMIN_USER_ID).partner_id.phone
            rec.web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            rec.registration_number = self.env['ir.config_parameter'].sudo().get_param('asterisk_plus.registration_number')

    def make_api_request(self, path, method, data={}, headers={}, raise_on_error=False):
        url = self.env['ir.config_parameter'].get_param(
            'asterisk_plus.registration_url', 'https://api1.oduist.com/instance/')
        if not url.endswith('/'):
            url = '{}/'.format(url)
        res = None
        try:
            res = method(urljoin(url, path), json=data, headers=headers)
            if res.status_code == 200:
                res = res.json()
                if res.get('error'):
                    raise ValidationError(res['error'])
                return res
            else:
                raise ValidationError(res.text)
        except Exception as e:
            if raise_on_error:
                raise ValidationError(str(e))
            else:
                return {}

    @api.model
    def set_instance_uid(self, instance_uid=False):
        existing_uid = self.env['ir.config_parameter'].get_param('asterisk_plus.instance_uid')
        if not existing_uid:
            if not instance_uid:
                instance_uid = str(uuid.uuid4())
            self.env['ir.config_parameter'].set_param('asterisk_plus.instance_uid', instance_uid)

    def register_instance(self):
        if not self.env.user.has_group('base.group_system'):
            raise ValidationError('Only Odoo admin can do it!')
        if self.get_param('is_registered'):
            raise ValidationError('This instance is already registered!')
        data = self.prepare_registration_data()
        if not data.get('customer_code'):
            raise ValidationError('Enter your customer code!')
        required_fields = [
            'admin_email', 'admin_name', 'admin_phone', 'company_name', 'company_city', 'company_email',
            'company_phone', 'company_country_code', 'company_country_name', 'installation_date', 'module_name',
            'module_version', 'url', 'odoo_version']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
        res = self.make_api_request('registration', requests.post, data=data, raise_on_error=True)
        if not res and self.get_param('api_fallback_url'):
            # Make a request and give error if fallback API endpoint is not available.
            logger.warning('Making a request to API fallback.')
            res = self.make_api_request(self.get_param('api_fallback_url'), requests.post, data=data, raise_on_error=True)
        self.env['ir.config_parameter'].sudo().set_param(
            'asterisk_plus.registration_key', res.get('registration_key'))
        self.env['ir.config_parameter'].sudo().set_param(
            'asterisk_plus.registration_number', res.get('registration_number'))
        self.set_param('is_registered', True)

    def prepare_registration_data(self):
        return {
            'instance_uid': self.get_param('instance_uid'),
            'company_name': self.get_param('company_name'),
            'company_country': self.get_param('company_country'),
            'company_state_name': self.get_param('company_state_name'),
            'company_country_code': self.get_param('company_country_code'),
            'company_country_name': self.get_param('company_country_name'),
            'company_email': self.get_param('company_email'),
            'company_city': self.get_param('company_city'),
            'company_phone': self.get_param('company_phone'),
            'admin_name': self.get_param('admin_name'),
            'admin_email': self.get_param('admin_email'),
            'admin_phone': self.get_param('admin_phone'),
            'module_version': self.get_param('module_version'),
            'module_name': MODULE_NAME,
            'odoo_version': self.get_param('odoo_version'),
            'odoo_full_version': release.version,
            'url': self.get_param('web_base_url'),
            'installation_date': self.get_param('installation_date').strftime("%Y-%m-%d"),
            'customer_code': self.get_param('customer_code'),
        }

    def update_company_data_button(self):
        main_company = self.env.company
        if not main_company:
            raise UserError("No main company found.")
        return {
            'type': 'ir.actions.act_window',
            'name': main_company.name,
            'res_model': 'res.company',
            'view_mode': 'form',
            'res_id': main_company.id,
            'target': 'new',
        }

    def update_admin_data_button(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env.user.partner_id.name,
            'res_model': 'res.partner',
            'view_mode': 'form',
            'res_id': self.env.user.partner_id.id,
            'target': 'new',
        }

    @api.model
    def get_instance_support_data(self):
        return False

    @api.model
    def set_defaults(self):
        # Called on installation to set default value
        api_url = self.get_param('api_url')
        if not api_url:
            # Set default value
            self.env['ir.config_parameter'].set_param(
                'asterisk_plus.api_url', 'https://api1.oduist.com')
        api_fallback_url = self.get_param('api_fallback_url')
        if not api_fallback_url:
            # Set default value
            self.env['ir.config_parameter'].set_param(
                'asterisk_plus.api_fallback_url', 'https://api2.oduist.com/')
        installation_date = self.env['ir.config_parameter'].sudo().get_param('asterisk_plus.installation_date')
        if not installation_date:
            installation_date = fields.Datetime.now()
            self.env['ir.config_parameter'].set_param('asterisk_plus.installation_date', installation_date)

    @api.model
    def _get_name(self):
        for rec in self:
            rec.name = 'General Settings'

    @api.model_create_multi
    def create(self, vals_list):
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()
        return super(Settings, self).create(vals_list)

    def write(self, vals):
        if vals.get('openai_api_key_display'):
            # Hide API key from WEB.
            vals['openai_api_key'] = vals['openai_api_key_display']
            vals['openai_api_key_display'] = '*' * len(vals['openai_api_key_display'])
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()
        return super(Settings, self).write(vals)

    def open_settings_form(self):
        rec = self.env['asterisk_plus.settings'].search([])
        if not rec:
            rec = self.sudo().with_context(no_constrains=True).create({})
        else:
            rec = rec[0]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'asterisk_plus.settings',
            'res_id': rec.id,
            'name': 'General Settings',
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    @ormcache('param')
    def get_param(self, param, default=False):
        self.check_access_rule('read') if release.version_info[0] < 18 else self.check_access('read')
        data = self.search([])
        if not data:
            data = self.sudo().with_context(no_constrains=True).create({})
        else:
            data = data[0]
        return getattr(data, param, default)

    @api.model
    def set_param(self, param, value, keep_existing=False):
        self.check_access_rule('write') if release.version_info[0] < 18 else self.check_access('write')
        data = self.search([])
        if not data:
            data = self.sudo().with_context(no_constrains=True).create({})
        else:
            data = data[0]
        # Check if the param is already there.
        if not keep_existing or not getattr(data, param):
            # TODO: How to handle Boolean fields!?
            setattr(data, param, value)
        else:
            debug(self, "Keeping existing value for param: {}".format(param))
        return True

    @api.model
    def asterisk_plus_notify(self, message, title='PBX', notify_uid=None,
                             sticky=False, warning=False):
        """Send a notification to logged in Odoo user.

        Args:
            message (str): Notification message.
            title (str): Notification title. If not specified: PBX.
            uid (int): Odoo user UID to send notification to. If not specified: calling user UID.
            sticky (boolean): Make a notiication message sticky (shown until closed). Default: False.
            warning (boolean): Make a warning notification type. Default: False.
        Returns:
            Always True.
        """
        # Use calling user UID if not specified.
        if not notify_uid:
            notify_uid = self.env.uid

        if release.version_info[0] < 15:
            self.env['bus.bus'].sendone(
                'asterisk_plus_actions_{}'.format(notify_uid),
                {
                    'action': 'notify',
                    'message': message,
                    'title': title,
                    'sticky': sticky,
                    'warning': warning
                })
        else:
            self.env['bus.bus']._sendone(
                'asterisk_plus_actions_{}'.format(notify_uid),
                'asterisk_plus_notify',
                {
                    'message': message,
                    'title': title,
                    'sticky': sticky,
                    'warning': warning
                })

        return True

    @api.model
    def asterisk_plus_reload_view(self, model):
        if release.version_info[0] < 15:
            msg = {
                'action': 'reload_view',
                'model': model,
            }
            self.env['bus.bus'].sendone('asterisk_plus_actions', json.dumps(msg))
        else:
            msg = {'model': model}
            self.env['bus.bus']._sendone(
                'asterisk_plus_actions',
                'reload_view',
                msg
            )

    @api.constrains('record_calls')
    def record_calls_toggle(self):
        if 'no_constrains' in self.env.context:
            return
        # Enable/disable call recording event
        recording_event = self.env.ref('asterisk_plus.var_set_mixmon')
        # Check if enent can be updated
        if recording_event.update == 'no':
            raise ValidationError(
                'Event {} is not updatebale'.format(recording_event.name))
        recording_event.is_enabled = True if self.record_calls is True else False
        # Reload events map
        servers = self.env['asterisk_plus.server'].search([])
        for s in servers:
            s.ami_action(
                {'Action': 'ReloadEvents'},
            )

    @api.onchange('use_mp3_encoder')
    def on_change_mp3_encoder(self):
        if 'no_constrains' in self.env.context:
            return
        for rec in self:
            if rec.use_mp3_encoder:
                rec.mp3_encoder_bitrate = '96'
                rec.mp3_encoder_quality = '4'

    @api.constrains('recordings_access_url')
    def _check_trailing_recordings_access_url_slash(self):
        if isinstance(self.recordings_access_url, str) and not self.recordings_access_url.endswith('/'):
            raise ValidationError('Recording Access URL must end with a slash!')

