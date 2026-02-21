# -*- coding: utf-8 -*

from datetime import datetime, timedelta
import json
import logging
import pytz
import uuid
import phonenumbers
import time
from odoo import models, fields, api, tools, release
from odoo.api import SUPERUSER_ID
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT
from .settings import debug

logger = logging.getLogger(__name__)


class Call(models.Model):
    _name = 'asterisk_plus.call'
    if release.version_info[0] < 11:
        _inherit = ['mail.thread']
    else:
        _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Call Detail Record'
    _order = 'id desc'
    _log_access = False
    _rec_name = 'id'

    if release.version_info[0] >= 17.0:
        # Fix for Odoo 17.0 write date field.
        write_date = fields.Datetime('Last Modified', readonly=True, copy=False, default=fields.Datetime.now)
    name = fields.Char(compute='_get_name')
    uniqueid = fields.Char(size=64, index=True)
    import_id = fields.Integer()
    server = fields.Many2one('asterisk_plus.server', ondelete='cascade')
    events = fields.One2many('asterisk_plus.call_event', inverse_name='call')
    calling_number = fields.Char(index=True, readonly=True, string='Partner Number')
    callerid_name = fields.Char()
    calling_name = fields.Char(compute='_get_calling_name', store=True)
    called_number = fields.Char(index=True, readonly=True)
    started = fields.Datetime(index=True, readonly=True)
    answered = fields.Datetime(index=True, readonly=True)
    ended = fields.Datetime(index=True, readonly=True)
    direction = fields.Selection(selection=[('in', 'Incoming'), ('out', 'Outgoing')],
        index=True, readonly=True)
    direction_icon = fields.Html(string='D', compute='_get_direction_icon')
    status = fields.Selection(selection=[
         ('noanswer', 'No Answer'), ('answered', 'Answered'),
         ('busy', 'Busy'), ('ended', 'Ended'), ('failed', 'Failed'),
         ('progress', 'In Progress')], index=True, default='progress')
    # Boolean index for split all calls on this flag. Calls are by default in active state.
    is_active = fields.Boolean(index=True, default=True)
    channels = fields.One2many('asterisk_plus.channel', inverse_name='call', readonly=True)
    recordings = fields.One2many('asterisk_plus.recording', inverse_name='call', readonly=True)
    recording_icon = fields.Html(compute='_get_recording_icon', string='R')
    partner = fields.Many2one('res.partner', ondelete='set null')
    partner_img = fields.Binary(related='partner.image'
      if release.version_info[0] < 13 else 'partner.image_1920', string="Partner Image")
    calling_user = fields.Many2one('res.users', ondelete='set null', readonly=False)
    calling_user_img = fields.Binary(related='calling_user.image'
      if release.version_info[0] < 13 else 'calling_user.image_1920', string="Calling User Image")
    answered_user = fields.Many2one('res.users', ondelete='set null', readonly=False)
    answered_user_img = fields.Binary(related='answered_user.image'
          if release.version_info[0] < 13 else 'answered_user.image_1920', string="Answered User Image")
    called_users = fields.Many2many('res.users', readonly=True)
    calling_avatar = fields.Text(compute='_get_calling_avatar', readonly=True)
    # Related object
    model = fields.Char(index=True)
    res_id = fields.Integer(index=True)
    ref = fields.Reference(
        string='Reference',
        selection=[
            ('res.partner', 'Partners'),
            ('asterisk_plus.call', 'Calls'),
            ('asterisk_plus.user', 'Users')],
        compute='_get_ref',
        inverse='_set_ref')
    ref_name = fields.Char(compute='_get_ref_name')
    notes = fields.Html()
    duration = fields.Integer(readonly=True, compute='_get_duration', store=True)
    duration_minutes = fields.Float(readonly=True, digits=(16,2), compute='_get_duration', store=True)
    duration_human = fields.Char(
        string='Call Duration',
        compute='_get_duration_human',
        store=True)
    voicemail_icon = fields.Html(compute='_get_voicemail_widget', string='V')
    voicemail_filename = fields.Char(readonly=True, index=True)
    voicemail_data = fields.Binary(attachment=True, readonly=True, string='Download')
    if release.version_info[0] >= 17.0:
        voicemail_widget = fields.Html(compute='_get_voicemail_widget', string='VoiceMail', sanitize=False)
    else:
        voicemail_widget = fields.Char(compute='_get_voicemail_widget', string='VoiceMail')
    has_voicemail = fields.Boolean(index=True, compute='_get_has_voicemail', store=True)
    is_transfer = fields.Boolean(index=True)
    is_transfer_icon = fields.Html(compute='_get_is_transfer_icon', string='T', store=True)
    is_stuck_active_call = fields.Boolean(index=True)

    @api.model_create_multi
    def create(self, vals_list):
        # Reload after call is created
        call = super(Call, self.with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True)).create(vals_list)
        self.reload_calls()
        return call

    def _get_name(self):
        for rec in self:
            if release.version_info[0] <= 11:
                started = fields.Datetime.context_timestamp(
                    rec, datetime.strptime(rec.started, '%Y-%m-%d %H:%M:%S'))
            else:
                started = fields.Datetime.context_timestamp(rec, rec.started)
            status = dict(self._fields['status'].selection).get(rec.status)
            direction = dict(self._fields['direction'].selection).get(rec.direction)
            formatted_time = fields.Datetime.to_string(started)
            rec.name = '{} {} call at {}'.format(status, direction, formatted_time)

    def _get_ref_name(self):
        for rec in self:
            try:
                if rec.ref:
                    rec.ref_name = '{}'.format(self.env[rec.model].browse(rec.res_id).name)
                else:
                    rec.ref_name = ''
            except Exception:
                rec.ref_name = ''

    @api.depends('callerid_name', 'partner')
    def _get_calling_name(self):
        for rec in self:
            # If there is a partner take the partner name.
            if rec.partner:
                rec.calling_name = rec.partner.name
            elif rec.callerid_name == '<unknown>':
                rec.calling_name = ''
            else:
                rec.calling_name = rec.callerid_name

    def _get_recording_icon(self):
        if release.version_info[0] <= 10:
            icon_data = 'R'
        else:
            icon_data = '<span class="fa fa-file-sound-o"/>'
        for rec in self:
            if rec.recordings:
                rec.recording_icon = icon_data
            else:
                rec.recording_icon = ''

    def _get_voicemail_widget(self):
        if release.version_info[0] <= 10:
            icon_data = 'V'
        else:
            icon_data = '<span class="fa fa-envelope-o"/>'
        voicemail_widget = '<audio id="sound_file" preload="auto" ' \
            'controls="controls"> ' \
            '<source src="/web/content?model=asterisk_plus.call&' \
            'id={call_id}&filename={filename}&field=voicemail_data&' \
            'filename_field=voicemail_filename&download=True" />' \
            '</audio>'
        for rec in self:
            if rec.voicemail_data:
                rec.voicemail_icon = icon_data
                rec.voicemail_widget = voicemail_widget.format(
                    call_id=rec.id,
                    filename=rec.voicemail_filename)
            else:
                rec.voicemail_icon = ''
                rec.voicemail_widget = ''

    @api.depends('voicemail_data')
    def _get_has_voicemail(self):
        for rec in self:
            rec.has_voicemail = bool(rec.voicemail_data)

    def update_reference(self, **kwargs):
        """Inherit in other modules to update call reference.
        """
        self.ensure_one()

    @api.constrains('is_active')
    def reload_on_hangup(self):
        """Reloads active calls list view after hangup.
        """
        for rec in self:
            if not rec.is_active:
                self.reload_calls()

    def notify_called_user(self, asterisk_user):
        """Notify user about incomming call.
        """
        # Open partner or reference form
        self._open_reference_form(asterisk_user)
        if not self.started:
            # Sometimes we don't have started set, need to trace more but for now just workaround.
            return False
        # Convert call started time using user timezone
        tz = pytz.timezone(asterisk_user.user.tz or 'UTC')
        call_started = self.started.replace(
            tzinfo=pytz.timezone('UTC')).astimezone(tz)

        ref_block = ''
        if self.ref and hasattr(self.ref, 'name'):
            ref_block = """
                <p class="text-center"><strong>Reference:</strong>
                <a href='/web#id={}&model={}&view_type=form'>
                    {}
                </a>
                </p>
            """.format(
                    self.res_id,
                    self.model,
                    self.ref.name)
        # If not ref and partner use partner as a link
        if not ref_block and self.partner:
            ref_block = """
                <p class="text-center"><strong>Partner:</strong>
                <a href='/web#id={}&model={}&view_type=form'>
                    {}
                </a>
                </p>
            """.format(
                    self.partner.id,
                    'res.partner',
                    self.partner.name)
        message = """
        <div class="d-flex align-items-center justify-content-center">
            <div>
                <img style="max-height: 100px; max-width: 100px;"
                        class="rounded-circle"
                        src={}/>
            </div>
            <div>
                <p class="text-center">Incoming call at {}</p>
                {}
            </div>
        </div>
        """.format(
                self.calling_avatar,
                call_started.strftime("%H:%M:%S"),
                ref_block)
        # Check user notify settings.
        if asterisk_user.call_popup_is_enabled:
            self.env['asterisk_plus.settings'].asterisk_plus_notify(
                message,
                notify_uid=asterisk_user.user.id,
                sticky=asterisk_user.call_popup_is_sticky)

    def _open_reference_form(self, asterisk_user):
        """Open partner or reference form."""
        if not asterisk_user.open_reference:
            return
        # We have model and res_id when reference is found
        model = self.model or 'res.partner'
        res_id = self.res_id or self.partner.id

        if not res_id:
            return

        if release.version_info[0] < 15:
            msg = {
                'action': 'open_record',
                'model': model,
                'res_id': res_id
            }
            self.env['bus.bus'].sendone(
                'asterisk_plus_actions_{}'.format(asterisk_user.user.id),
                json.dumps(msg))
        else:
            self.env['bus.bus']._sendone(
                'asterisk_plus_actions_{}'.format(asterisk_user.user.id),
                'open_record',
                {'model': model, 'res_id': res_id}
            )

    @api.depends('model', 'res_id')
    def _get_ref(self):
        # We need a reference field to be computed because we want to
        # search and group by model.
        for rec in self:
            if rec.model and rec.model in self.env:
                try:
                    rec.ref = '%s,%s' % (rec.model, rec.res_id or 0)
                except ValueError as e:
                    logger.warning(e)
                    rec.ref = None
            else:
                rec.ref = None

    def _set_ref(self):
        for rec in self:
            if rec.ref:
                rec.write({'model': rec.ref._name, 'res_id': rec.ref.id})
            else:
                rec.write({'model': False, 'res_id': False})

    def _get_calling_avatar(self):
        """Get avatar for calling user.
        """
        for rec in self:
            if rec.partner:
                rec.calling_avatar = '/web/image/{}/{}/image_1024'.format(rec.partner._name, rec.partner.id)
            elif rec.calling_user:
                rec.calling_avatar = '/web/image/{}/{}/image_1024'.format(rec.calling_user._name, rec.calling_user.id)
            else:
                rec.calling_avatar = '/web/image'

    def _get_direction_icon(self):
        for rec in self:
            rec.direction_icon = '<span class="fa fa-arrow-left"/>' if rec.direction == 'in' else \
                '<span class="fa fa-arrow-right"/>'

    def reload_calls(self, data=None):
        """Reloads active calls list view.
        Returns: None.
        """
        auto_reload = self.env[
            'asterisk_plus.settings'].sudo().get_param('auto_reload_calls')
        if not auto_reload:
            return
        if data is None:
            data = {}
        if release.version_info[0] < 15:
            msg = {
                'action': 'reload_view',
                'model': 'asterisk_plus.call'
            }
            self.env['bus.bus'].sendone('asterisk_plus_actions', json.dumps(msg))
        else:
            msg = {'model': 'asterisk_plus.call'}
            self.env['bus.bus']._sendone(
                'asterisk_plus_actions',
                'reload_view',
                msg
            )

    def set_notes(self):
        return {
            'name': "Set Note",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'asterisk_plus.set_notes_wizard',
            'target': 'new',
            'context': {'default_notes': self.notes}
        }

    @api.model
    def delete_calls(self):
        # Cron job to delete calls history.
        days = self.env[
            'asterisk_plus.settings'].get_param('calls_keep_days')
        expire_date = datetime.utcnow() - timedelta(days=int(days))
        expired_calls = self.env['asterisk_plus.call'].search([
            ('started', '<=', expire_date.strftime('%Y-%m-%d %H:%M:%S'))
        ], order='id asc')
        logger.info('Expired {} calls'.format(len(expired_calls)))
        batch_size = 10
        while expired_calls:
            batch = expired_calls[:batch_size]
            expired_calls -= batch
            ids = [k.id for k in batch]
            logger.info('Deleteing IDS: {}'.format(ids))
            # Hack to deal with 1 record
            if len(ids) == 1:
                ids = [ids[0], ids[0]]
            q_messages = "DELETE FROM mail_message where model = 'asterisk_plus.call' AND res_id IN {}".format(tuple(ids))
            q_activity = "DELETE FROM mail_activity where res_model = 'asterisk_plus.call' AND res_id IN {}".format(tuple(ids))
            q_calls = "DELETE FROM asterisk_plus_call WHERE id  IN {}".format(tuple(ids))
            for q in [q_messages, q_activity, q_calls]:
                self.env.cr.execute(q)
                self.env.cr.commit()
            # Give transactions a way to be completed
            time.sleep(0.1)

    @api.model
    def cleanup_active_calls(self):
        # Cron job to move hang calls to history
        expire_date = datetime.utcnow() - timedelta(hours=2)
        hang_calls = self.env['asterisk_plus.call'].search([
            ('is_active', '=', True),
            ('started', '<=', expire_date.strftime('%Y-%m-%d %H:%M:%S'))
        ])
        # We assume the call was 5 minutes (just an average).
        hang_calls.move_to_history()
        logger.info('Moved %s calls into history.', len(hang_calls))

    def move_to_history(self):
        # Mark a call as ended (for hang calls)
        for rec in self:
            rec.write({
                'is_active': False,
                'ended': rec.started,
                'answered': rec.started,
                'status': 'ended',
                'is_stuck_active_call': True,
            })

    @api.depends('answered', 'ended')
    def _get_duration(self):
        for rec in self:
            if rec.answered and rec.ended:
                if release.version_info[0] > 11:
                    seconds = (rec.ended - rec.answered).total_seconds()
                    rec.duration = seconds
                    rec.duration_minutes = seconds / 60.0
                else:
                    seconds = (
                        datetime.strptime(rec.ended, DATETIME_FORMAT) - \
                            datetime.strptime(rec.answered, DATETIME_FORMAT)).total_seconds()
                    rec.duration = seconds
                    rec.duration_minutes = seconds / 60.0

    @api.depends('duration')
    def _get_duration_human(self):
        for rec in self:
            rec.duration_human = str(timedelta(seconds=rec.duration))

    @api.constrains('is_active')
    def save_call_recordings(self):
        # Check if call recording is enabled and save record
        if self.env['asterisk_plus.settings'].sudo().get_param('record_calls'):
            for rec in self:
                self.env['asterisk_plus.recording'].save_call_recordings(rec)

    @api.constrains('is_active')
    def register_call(self):
        def sub_register_call(obj, **kwargs):
            if obj:
                try:
                    if release.version_info[0] < 13:
                        obj.sudo(SUPERUSER_ID).with_context(mail_create_nosubscribe=False).message_post(**kwargs)
                    else:
                        obj.with_user(SUPERUSER_ID).with_context(mail_create_nosubscribe=False).message_post(**kwargs)
                except Exception:
                    logger.exception('Register call error: ')
        self.ensure_one()
        if self.is_active:
            return
        notify_users = []
        # Constract message from lines
        message = [self.name]
        if self.calling_user:
            message.append('from user {}'.format(self.calling_user.name))
        if self.duration:
            message.append('duration: {}'.format(self.duration_human))
        if self.answered_user:
            message.append('answered by {}'.format(self.answered_user.name))
        if self.called_users:
            message.append('dialed users {}'.format(','.join(k.name for k in self.called_users)))
            # Missed call notification, filter users who have it enabled.
            for user in self.called_users:
                if user.asterisk_users[0].missed_calls_notify:
                    notify_users.append(user)
        # Register call at partner or reference object
        if self.partner and self.model != 'res.partner':
            sub_register_call(self.partner, body=' '.join(message), subtype_xmlid='mail.mt_note')
            message.insert(1, 'partner {}'.format(self.partner.name))
        if self.ref:
            sub_register_call(self.ref, body=' '.join(message), subtype_xmlid='mail.mt_note')
            message.insert(2, 'ref {}'.format(self.ref.name))
        # Register call to users
        if self.direction == 'in' and self.status != 'answered' and notify_users:
            debug(self, 'Missed call notification to users: {}'.format(notify_users))
            sub_register_call(
                self,
                subtype_xmlid='mail.mt_comment',
                subject=self.name,
                body=' '.join(message),
                partner_ids=[k.partner_id.id for k in notify_users]
            )


    def partner_button(self):
        self.ensure_one()
        context = {}
        if not self.partner:
            # Create a new parter
            self.partner = self.env['res.partner'].with_context(
                call_id=self.id).create({'name': self.calling_name or self.calling_number})
            context['form_view_initial_mode'] = 'edit'
        # Open call partner form.
        if self.partner:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'res_id': self.partner.id,
                'name': 'Call Partner',
                'view_mode': 'form',
                'target': 'current',
                'context': context,
            }
        else:
            raise ValidationError('Partner is already defined!')

    def _spy(self, option):
        self.ensure_one()
        asterisk_user = self.env.user.asterisk_users.filtered(
            lambda x: x.server == self.server)
        if not asterisk_user:
            raise ValidationError('PBX user is not configured!')
        if not asterisk_user.channels:
            raise ValidationError('User has not channels to originate!')
        # Get the extension/agent channel for spy.
        # For inbound calls the agent channel is the child (has parent_channel).
        # For outbound calls the agent channel is the parent (no parent_channel).
        if self.direction == 'in':
            channel = self.channels.filtered(
                lambda x: x.parent_channel and x.is_active)
        else:
            channel = self.channels.filtered(lambda x: not x.parent_channel)
        channel = channel[:1]
        if not channel:
            raise ValidationError('Channel for spy not found!')
        if option == 'q':
            callerid = 'Spy'
        elif option == 'qw':
            callerid = 'Whisper'
        elif option == 'qB':
            callerid = 'Barge'
        else:
            callerid = 'Unknown'
        for user_channel in asterisk_user.channels:
            if not user_channel.originate_enabled:
                logger.info('User %s channel %s not enabled to originate.',
                            self.env.user.id, user_channel.name)
                continue
            # Create a channel and set no_call so that no calls are created.
            channel_id = uuid.uuid4().hex
            self.env['asterisk_plus.channel'].create({
                'uniqueid': channel_id,
                'no_call': True,
                'is_active': True,
                'server': asterisk_user.server.id,
            })
            self.env.cr.commit()
            action = {
                'ChannelId': channel_id,
                'Action': 'Originate',
                'Async': 'true',
                'Callerid': '{} <1234567890>'.format(callerid, channel.exten),
                'Channel': user_channel.name,
                'Application': 'ChanSpy',
                'Data': '{},{}'.format(channel.channel, option),
                'Variable': asterisk_user._get_originate_vars()
            }
            user_channel.server.ami_action(action, res_notify_uid=self.env.uid)

    def listen(self):
        self._spy('q')

    def whisper(self):
        self._spy('qw')

    def barge(self):
        self._spy('qB')

    @api.model
    def on_user_event_set_answered(self, event):
        debug(self, 'Call Answered UserEvent')
        call = self.search([('uniqueid', '=', event['Uniqueid'])])
        if call:
            call.status = 'answered'
        else:
            logger.warning('Call ID %s not found to set CallAnswered UserEvent!', event['Uniqueid'])
        return True

    @api.model
    def on_user_event_set_transfer(self, event):
        call = self.search(['|',
            ('uniqueid', '=', event['Uniqueid']),
            ('uniqueid', '=', event['Linkedid'])])
        if call:
            if event.get('status') == '1':
                call.is_transfer = True
                debug(self, 'Call SetTransfer = True UserEvent')
            else:
                call.is_transfer = False
                debug(self, 'Call SetTransfer = False UserEvent')
            return True
        else:
            debug(self,
                  'Call ID %s not found to set SetTransfer UserEvent!' % event['Uniqueid'])
            return False

    @api.depends('is_transfer')
    def _get_is_transfer_icon(self):
        if release.version_info[0] <= 10:
            icon_data = 'T'
        else:
            icon_data = '<span class="fa fa-mail-forward"/>'
        for rec in self:
            if rec.is_transfer:
                rec.is_transfer_icon = icon_data
            else:
                rec.is_transfer_icon = ''
