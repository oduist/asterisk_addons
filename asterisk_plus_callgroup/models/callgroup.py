from datetime import datetime
import logging
import os
import re
from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.addons.asterisk_plus.models.settings import debug

logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r'^\+?\d+$')

class Callgroup(models.Model):
    _inherit = 'mail.thread'
    _name = 'asterisk_plus.callgroup'
    _description = 'Call Group'

    name = fields.Char(required=True, tracking=True,
        readonly=False, related='partner_id.name', store=True)
    partner_id = fields.Many2one('res.partner', ondelete='restrict', required=True)
    calls_count = fields.Integer(compute='_get_calls_count')
    calls = fields.One2many('asterisk_plus.call', 'callgroup')
    external_phone = fields.Char(related='partner_id.mobile', readonly=False, store=True,
                                string='External Phone')
    internal_phone = fields.Char(required=True, related='partner_id.phone',
                                 readonly=False, store=True, string='Internal Phone')
    fallback_group = fields.Many2one('asterisk_plus.callgroup', tracking=True)
    users = fields.Many2many('res.users', tracking=True)
    users_list = fields.Char(compute='_get_users', store=True, tracking=True)
    timeout = fields.Integer(required=True, default=60, tracking=True)
    dispatcher = fields.Many2one('res.users', tracking=True)
    record_calls = fields.Boolean()
    # Prompt 1
    callgroup_voicemail_prompt1 = fields.Binary(attachment=True)
    prompt_filename1 = fields.Char(tracking=True)
    voicemail_widget1 = fields.Char(compute='_get_voicemail_widget',
                                   string='VoiceMail Prompt')
    # Prompt 2
    callgroup_voicemail_prompt2 = fields.Binary(attachment=True)
    prompt_filename2 = fields.Char(tracking=True)
    voicemail_widget2 = fields.Char(compute='_get_voicemail_widget',
                                   string='VoiceMail Prompt')
    # Prompt 3
    callgroup_voicemail_prompt3 = fields.Binary(attachment=True)
    prompt_filename3 = fields.Char(tracking=True)
    voicemail_widget3 = fields.Char(compute='_get_voicemail_widget',
                                   string='VoiceMail Prompt')
    #
    active_prompt = fields.Selection(selection=
        [(str(k), 'Prompt %s' % k) for k in range(1,4)],
        required=False, tracking=True)

    def _get_voicemail_widget(self):
        for rec in self:
            rec.voicemail_widget1 = '<audio id="sound_file" preload="auto" ' \
                'controls="controls"> ' \
                '<source src="/web/content?model=asterisk_plus.callgroup&' \
                'id={rec_id}&filename={filename}&field=callgroup_voicemail_prompt1&' \
                'filename_field=prompt_filename1&download=True" />' \
                '</audio>'.format(
                    rec_id=rec.id,
                    filename=rec.prompt_filename1)
            rec.voicemail_widget2 = '<audio id="sound_file" preload="auto" ' \
                'controls="controls"> ' \
                '<source src="/web/content?model=asterisk_plus.callgroup&' \
                'id={rec_id}&filename={filename}&field=callgroup_voicemail_prompt2&' \
                'filename_field=prompt_filename2&download=True" />' \
                '</audio>'.format(
                    rec_id=rec.id,
                    filename=rec.prompt_filename2)
            rec.voicemail_widget3 = '<audio id="sound_file" preload="auto" ' \
                'controls="controls"> ' \
                '<source src="/web/content?model=asterisk_plus.callgroup&' \
                'id={rec_id}&filename={filename}&field=callgroup_voicemail_prompt3&' \
                'filename_field=prompt_filename3&download=True" />' \
                '</audio>'.format(
                    rec_id=rec.id,
                    filename=rec.prompt_filename3)

    @api.model
    def create(self, vals):
        partner = self.env['res.partner'].create({
            'name': vals['name'],
        })
        vals['partner_id'] = partner.id
        return super().create(vals)

    def unlink(self):
        # Remove prompts
        ids = [k.id for k in self]
        for _id in ids:
            self.delete_voicemail_prompt(_id, 1)
            self.delete_voicemail_prompt(_id, 2)
            self.delete_voicemail_prompt(_id, 3)
        # Remove res.partner links.
        for rec in self:
            partner = rec.partner_id
            super(Callgroup, rec).unlink()
            if partner:
                partner.unlink()
        return True

    def write(self, vals):
        # Transform number
        def normalize_phone(number):
            return number.replace(' ', '').replace('(', '').replace(')','').replace('-','')

        for k in ['external_phone', 'internal_phone']:
            if vals.get(k):
                vals[k] = normalize_phone(vals[k])
                if not PHONE_RE.search(vals[k]):
                    raise ValidationError('Phone number must include only digits!')
        return super().write(vals)

    @api.constrains('name')
    def check_callgroup_name(self):
        for rec in self:
            if rec.name and ' ' in rec.name:
                raise ValidationError('Spaces are not allowed in call group name!')

    @api.constrains('prompt_filename1', 'prompt_filename2', 'prompt_filename3')
    def check_prompt_filename(self):
        def check_prompt_name(name):
            _, ext = os.path.splitext(name)
            if ext.lower() not in ['.mp3', '.wav']:
                raise ValidationError('Only mp3 and wav files are supported!')
        for rec in self:
            for filename in [rec.prompt_filename1, rec.prompt_filename3, rec.prompt_filename3]:
                if filename:
                    check_prompt_name(filename)

    @api.constrains('prompt_filename2')
    def _check_prompt_filename2(self):
        for rec in self:
            if rec.prompt_filename2:
                self._check_name(rec.prompt_filename2)

    @api.constrains('prompt_filename3')
    def _check_prompt_filename3(self):
        for rec in self:
            if rec.prompt_filename3:
                self._check_name(rec.prompt_filename3)

    def _get_calls_count(self):
        for rec in self:
            rec.calls_count = self.env['asterisk_plus.call'].search_count(
                [('callgroup', '=', rec.id)])

    def put_voicemail_prompts(self):
        if self.callgroup_voicemail_prompt1:
            self.put_voicemail_prompt(self.id, 1)
        else:
            self.delete_voicemail_prompt(self.id, 1)
        if self.callgroup_voicemail_prompt2:
            self.put_voicemail_prompt(self.id, 2)
        else:
            self.delete_voicemail_prompt(self.id, 2)
        if self.callgroup_voicemail_prompt3:
            self.put_voicemail_prompt(self.id, 3)
        else:
            self.delete_voicemail_prompt(self.id, 3)

    def put_voicemail_prompt(self, rec_id, prompt_id):
        self.ensure_one()
        if not rec_id:
            rec_id = self.id
        try:
            self.env.ref('asterisk_plus.default_server').local_job(
                fun='download_prompt',
                args=['asterisk_plus.callgroup', rec_id,
                      'callgroup_voicemail_prompt{}'.format(prompt_id),
                      'prompt_filename{}'.format(prompt_id)],
                kwargs={}, res_notify_uid=self.env.uid)
        except Exception as e:
            logger.exception('Could not put voicemail prompt %s: %s', rec_id, e)

    def delete_voicemail_prompt(self, rec_id, prompt_id):
        try:
            self.env.ref('asterisk_plus.default_server').local_job(
                fun='delete_prompt',
                args=['asterisk_plus.callgroup', rec_id, 'callgroup_voicemail_prompt{}'.format(prompt_id)],
                kwargs={}, res_notify_uid=self.env.uid)
        except Exception as e:
            logger.exception('Could not remove voicemail prompt %s: %s', rec_id, e)

    @api.depends('users')
    def _get_users(self):
        for rec in self:
            rec.users_list = ', '.join([k.name for k in rec.users])

    @api.model
    def fagi_request(self, request):
        debug(self, 'AGI request: {}'.format(request))
        extension = request['agi_extension']
        # We put here transfer context
        agi_arg_1 = request.get('agi_arg_1', '')
        # Get call group number or fallback to extension.
        callgroup_number = extension
        agi_channel = request['agi_channel']
        channel = re.search('^(?P<channel>.+)-.+$', agi_channel).groupdict().get('channel')
        callerid = request['agi_callerid']
        # Find callgroup by dialed number
        callgroup = self.env['asterisk_plus.callgroup'].search(
            ['|', ('external_phone', '=', callgroup_number), ('internal_phone', '=', callgroup_number)],
            limit=1)
        if not callgroup:
            debug(self, 'No callgroup by number %s found.' % extension)
            return ['EXEC VERBOSE CALLGROUP_NOT_FOUND']
        # Set callgroup channel data
        last_callgroup_rec = self.env['asterisk_plus.channel_data'].search([
            ('uniqueid', '=', request['agi_uniqueid']),
            ('key', '=', 'callgroup_id'),
        ])
        if last_callgroup_rec:
            last_callgroup_id = int(last_callgroup_rec.value)
        else:
            self.env['asterisk_plus.channel_data'].create({
                'uniqueid': request['agi_uniqueid'],
                'key': 'callgroup_id',
                'value':  callgroup.id,
            })
            last_callgroup_id = callgroup.id
        last_callgroup = self.env['asterisk_plus.callgroup'].browse(last_callgroup_id)
        # Iterate over call group users and collect channels
        channels = []
        endpoints = []
        res = []
        for user in callgroup.users:
            for channel in user.asterisk_users.channels:
                channels.append(channel.name)
                endpoint = channel.name.split('/')[1]
                endpoints.append(endpoint)
        if not channels:
            logger.warning('Call group %s without users!', callgroup.name)
            return ['EXEC VERBOSE CALLGROUP_HAS_NO_USERS']
        debug(self, 'Callgroup {} dialing users {}'.format(callgroup.name, endpoints))
        res.append('EXEC ANSWER 500')
        if callgroup.record_calls:
            now = datetime.now()
            year = now.year
            month = now.month
            day = now.day
            res.append('EXEC MIXMONITOR {}/{}/{}/{}.wav,b'.format(year, month, day, request['agi_uniqueid']))
        # Check transfer context
        if agi_arg_1:
            agi_arg_1 = agi_arg_1.format('^{}'.format(last_callgroup.name))
        else:
            agi_arg_1 = 'b(callgroup-predial-handler^s^1({}))'.format(last_callgroup.name)
        res.append('PJSIP_DIAL_CONTACTS {} {},t{}'.format(
            ','.join(endpoints), callgroup.timeout, agi_arg_1))
        if callgroup.fallback_group:
            debug(self, 'Callgroup fallback to %s' % callgroup.fallback_group.name)
            # Restart the context with new group.
            if extension.startswith('+'):
                goto_number = callgroup.fallback_group.external_phone
            else:
                goto_number = callgroup.fallback_group.internal_phone
            res.append(
                'EXEC GOTO {},{},1'.format(
                    request['agi_context'], goto_number))
        elif callgroup.active_prompt:
            # We have a voicemail prompt, so playback and record the channel.
            debug(self, 'Callgroup %s voicemail active.', callgroup.name)
            if callgroup.record_calls:
                res.append('EXEC STOPMIXMONITOR')
            res.append('EXEC PLAYBACK callgroup_voicemail_prompt{}_{}'.format(callgroup.active_prompt, callgroup.id))
            res.append('EXEC MINIVMRECORD callgroup-{}@default'.format(callgroup.id))
            res.append('EXEC HANGUP')
        else:
            logger.warning('CallGroup %s: Nobody available, hangup.', callgroup.name)
            if callgroup.record_calls:
                res.append('EXEC STOPMIXMONITOR')
            res.append('EXEC PLAYBACK im-sorry')
            res.append('EXEC PLAYBACK vm-nobodyavail')
            res.append('EXEC MINIVMGREET callgroup-{}@default'.format(callgroup.id))
            res.append('EXEC MINIVMRECORD callgroup-{}@default'.format(callgroup.id))
            res.append('EXEC HANGUP')
        return res
