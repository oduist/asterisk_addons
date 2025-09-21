from datetime import datetime
import logging
import re
from odoo import models, fields, api, tools, release, release, SUPERUSER_ID, _
from odoo.exceptions import ValidationError, UserError
from passlib import pwd
from random import choice
from .server import get_default_server
from .settings import debug

logger = logging.getLogger(__name__)


#: Fields allowed to be changed by user.
USER_PERMITTED_FIELDS = [
    'open_reference', 'missed_calls_notify', 'call_popup_is_enabled',
    'call_popup_is_sticky', 'dial_timeout', 'phone', 'mobile',
]


class PbxUser(models.Model):
    _name = 'asterisk_plus.user'
    _inherit = 'mail.thread'
    _description = 'Asterisk User'

    active = fields.Boolean(default=True, tracking=True)
    exten = fields.Char()
    user = fields.Many2one('res.users', required=False,
                           ondelete='cascade',
                           # Exclude shared users
                           domain=[('share', '=', False)])
    name = fields.Char(related='user.name', readonly=True)
    phone = fields.Char(related='user.phone', readonly=False,
        help="User's phone from res.partner contact, change is reflected there.")
    phone_normalized = fields.Char(related='user.phone_normalized', readonly=True)
    mobile = fields.Char(related='user.mobile', readonly=False,
        help="User's mobile from res.partner contact, change is reflected there.")
    mobile_normalized = fields.Char(related='user.mobile_normalized', readonly=True)
    did_number = fields.Char('DID Number')
    callerid_number = fields.Char('CallerID Number')
    #: Server where the channel is defined.
    server = fields.Many2one('asterisk_plus.server', required=True,
                             ondelete='restrict', default=get_default_server)
    generate_sip_peers = fields.Boolean(related='server.generate_sip_peers')
    channels = fields.One2many('asterisk_plus.user_channel',
                               inverse_name='asterisk_user')
    originate_vars = fields.Text(string='Channel Variables')
    open_reference = fields.Boolean(
        default=True,
        help=_('Open reference form on incoming calls.'))
    user_call_count = fields.Integer(compute='_get_call_count', string='Calls')
    missed_calls_notify = fields.Boolean(
        default=True,
        help=_('Notify user on missed calls.'))
    call_popup_is_enabled = fields.Boolean(
        default=True,
        string='Call Popup')
    call_popup_is_sticky = fields.Boolean(
        default=False,
        string='Popup Is Sticky')
    # FAGI settings
    dial_timeout = fields.Integer(default=30, required=True)
    record_calls = fields.Boolean()

    _sql_constraints = [
        ('exten_uniq', 'unique (exten,server)',
         _('This phone extension is already used!')),
        ('user_uniq', 'unique ("user",server)',
         _('This user is already defined!')),
    ]

    @api.model
    def create(self, vals):
        pbx_user = super(PbxUser, self).create(vals)
        if pbx_user and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()

        if pbx_user.user and not pbx_user.user.has_group('asterisk_plus.group_asterisk_user'):
            group_asterisk_user = self.env.ref('asterisk_plus.group_asterisk_user')
            group_asterisk_user.write({'users': [(4, pbx_user.user.id)]})
        return pbx_user

    def write(self, vals):
        if not (self.env.user.has_group(
                'asterisk_plus.group_asterisk_admin') or
                self.env.user.id == SUPERUSER_ID):
            # User can only change some fields.
            restricted_fields = set(vals.keys()) - set(USER_PERMITTED_FIELDS)
            if restricted_fields:
                raise ValidationError(
                    _('Fields {} not allowed to be changed by user!').format(
                        ', '.join(restricted_fields)))
        user = super(PbxUser, self).write(vals)
        if user and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return user

    def unlink(self):
        res = super(PbxUser, self).unlink()
        if res and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    @api.model
    def has_asterisk_plus_group(self, user=None):
        """Used from actions.js to check if Odoo user is enabled to
        use Asterisk applications in order to start a bus listener.
        """
        if not user:
            user = self.env.user
        if (user.has_group('asterisk_plus.group_asterisk_admin') or
                user.has_group(
                    'asterisk_plus.group_asterisk_user')):
            return True

    def _get_originate_vars(self):
        self.ensure_one()
        res = set([
            '__REALCALLERIDNUM={}'.format(self.exten),
            '__CALLERIDNUMINTERNAL={}'.format(self.exten),
        ])
        try:
            if self.originate_vars:
                res.update([k for k in self.originate_vars.split('\n') if k])
        except Exception:
            logger.exception('Get originate vars error:')
        return list(res)

    def dial_user(self):
        self.ensure_one()
        self.env.user.asterisk_users[0].server.originate_call(
            self.exten, model='asterisk_plus.user', res_id=self.id)

    def open_user_form(self):
        if self.env.user.has_group('asterisk_plus.group_asterisk_admin'):
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'asterisk_plus.user',
                'name': 'Users',
                'view_mode': 'tree,form',
                'view_type': 'form',
                'target': 'current',
            }
        else:
            if not self.env.user.asterisk_users:
                raise ValidationError('PBX user is not configured!')
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'asterisk_plus.user',
                'res_id': self.env.user.asterisk_users.id,
                'name': 'User',
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'current',
            }

    @api.model
    def auto_create(self, users):
        """Auto create pbx user for every record in "users" recordset
        """
        server = self.env.ref('asterisk_plus.default_server')
        if not server.auto_create_pbx_users:
            debug(self, 'Auto create PBX users not enabled.')
            return
        extensions = {int(el) for el in self.search([]).mapped('exten') if el.isdigit()}
        if extensions:
            next_extension = max(extensions) + 1
        else:
            try:
                next_extension = int(self.env.ref('asterisk_plus.default_server').sip_peer_start_exten)
            except Exception as e:
                logger.exception('Wrong value for starting extension, taking 101.')
                next_extension = 101
        existing_users = self.env['asterisk_plus.user'].search([]).mapped('user')
        add_users = set(users) - set(existing_users)
        for user in add_users:
            # create SIP account only for PBX users.
            if not user.has_group('asterisk_plus.group_asterisk_user'):
                debug(self, 'Skip user {} as not in PBX user group.'.format(user.name))
                continue
            elif self.env['asterisk_plus.user'].search([('user', '=', user.id)]):
                debug(self, 'Skip PBX user {} as already created'.format(user.name))
                continue
            # create new pbx user
            debug(self, "Creating pbx user {} with extension {}".format(user.login, next_extension))
            asterisk_user = self.create([
                {'exten': "{}".format(next_extension), 'user': user.id},
            ])

            # Generate sip_user from user.login (without @domain) + user id
            sip_user = next_extension
            # create new channel for newly created user
            user_channel = self.env[
                'asterisk_plus.user_channel'].create({
                'name': '{}/{}'.format(server.sip_protocol, sip_user),
                'server': server.id,
                'asterisk_user': asterisk_user.id,
                'sip_user': sip_user,
                'sip_password': pwd.genword(length=choice(range(12,16))),
            })
            debug(self, 'Create sip_user {} id {} for {}'.format(user_channel.sip_user, user_channel.id, user.login))
            next_extension += 1

    def _get_call_count(self):
        for rec in self:
            rec.user_call_count = self.env[
                'asterisk_plus.call'].sudo().search_count(
                ['|', ('calling_user', '=', rec.user.id),
                      ('answered_user', '=', rec.user.id)])

    def action_view_calls(self):
        # Used from the user calls view button.
        self.ensure_one()
        return {
            'name': _("Calls"),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'res_model': 'asterisk_plus.call',
            'domain': ['|', ('calling_user', '=', self.user.id),
                            ('answered_user', '=', self.user.id)],
        }

    def set_channel_transport_wizard(self):
        return {
            'name': "Set Channel Transport Wizard",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'asterisk_plus.set_channel_transport_wizard',
            'target': 'new',
            'context': {'active_ids': [k.id for k in self]}
        }


    @api.model
    def fagi_request(self, request):
        debug(self, 'AGI request: {}'.format(request))
        extension = request['agi_extension']
        agi_channel = request['agi_channel']
        channel = re.search('^(?P<channel>.+)-.+$', agi_channel).groupdict().get('channel')
        callerid = request['agi_callerid']
        # Find destination users by personal number or exten
        users = self.env['asterisk_plus.user'].search(
            ['|', ('did_number', '=', extension), ('exten', '=', extension)])
        endpoints = []
        if len(users) == 1:
            user = users[0]
            debug(self, 'Found PBX user {} by phone {}'.format(user.name, extension))
            for channel in users.channels:
                endpoint = channel.name.split('/')[1]
                endpoints.append(endpoint)
            res = []
            if user.record_calls:
                now = datetime.now()
                year = now.year
                month = now.month
                day = now.day
                res.append('EXEC MIXMONITOR {}/{}/{}/{}.wav,b'.format(year, month, day, request['agi_uniqueid']))
            res.append('PJSIP_DIAL_CONTACTS {} {},t'.format(','.join(endpoints), user.dial_timeout))
            return res
        elif len(users) > 1:
            # Multiple users, no voicemail
            debug(self, 'Found many users {} by phone {}'.format(
                [k.name for k in users], extension))
            for user in users:
                for channel in users.channels:
                    endpoint = channel.name.split('/')[1]
                    endpoints.append(endpoint)
            return [
                'EXEC VERBOSE "Muliple users by number {} found."'.format(extension),
                'PJSIP_DIAL_CONTACTS {} {},t'.format(','.join(endpoints),user.dial_timeout)
            ]
        else:
            debug(self, 'No PBX user by number %s found.' % extension)
            return []

    def apply_sip_peers(self):
        # Send a message to Agent to download SIP peers
        if self.server.generate_sip_peers:
            self.server.local_job(fun='sip.get_peers', args=self.server.id, res_notify_uid=self.env.uid)
        else:
            raise ValidationError('SIP peers generation not enabled!')


