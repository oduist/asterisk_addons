import io
from datetime import datetime, timedelta
import requests
import sys
import time
from urllib.parse import urljoin, quote
import uuid
import logging
from odoo import models, fields, api, _, tools, release, release, SUPERUSER_ID
from odoo.exceptions import ValidationError
from .server import debug
from .settings import MODULE_NAME, RECORDING_ACCESS_SELECTION

logger = logging.getLogger(__name__)


class Recording(models.Model):
    _name = 'asterisk_plus.recording'
    _inherit = 'mail.thread'
    _description = 'Recording'
    _rec_name = 'id'
    _order = 'id desc'

    uniqueid = fields.Char(size=64, index=True, readonly=True)
    transcript_short = fields.Char(compute='_get_transcript_short')
    call = fields.Many2one('asterisk_plus.call', ondelete='set null', readonly=True)
    called_users = fields.Many2many(related='call.called_users')
    channel = fields.Many2one('asterisk_plus.channel', ondelete='set null', readonly=True)
    partner = fields.Many2one('res.partner', ondelete='set null', readonly=True)
    calling_user = fields.Many2one('res.users', ondelete='set null', readonly=True)
    answered_user = fields.Many2one('res.users', ondelete='set null', readonly=True)
    calling_number = fields.Char(index=True, readonly=True)
    calling_name = fields.Char(compute='_get_calling_name', readonly=True)
    called_number = fields.Char(index=True, readonly=True)
    answered = fields.Datetime(index=True, readonly=True)
    duration = fields.Integer(related='call.duration', store=True)
    duration_human = fields.Char(related='call.duration_human', store=True)
    if release.version_info[0] >= 17.0:
        recording_widget = fields.Html(compute='_get_recording_widget', string='Recording', sanitize=False)
    else:
        recording_widget = fields.Char(compute='_get_recording_widget', string='Recording')
    recording_filename = fields.Char(readonly=True, index=True)
    recording_data = fields.Binary(attachment=False, readonly=True, string=_('Download'))
    recording = fields.Binary(compute='_get_recording')
    recording_attachment = fields.Binary(attachment=True, readonly=True, string=_('Download'))
    recording_access = fields.Selection(selection=RECORDING_ACCESS_SELECTION)
    recording_access_url = fields.Char()
    file_path = fields.Char(readonly=True)
    tags = fields.Many2many('asterisk_plus.tag',
                            relation='asterisk_plus_recording_tag',
                            column1='tag', column2='recording')
    keep_forever = fields.Selection([
        ('no', 'Archivable'),
        ('yes', 'Keep Forever')
    ], default='no', tracking=True)
    icon = fields.Html(compute='_get_icon', string='I')
    ############## TRANSCRIPTION FIELDS ######################################
    transcript = fields.Text()
    transcription_token = fields.Char()
    transcription_error = fields.Char()
    transcription_price = fields.Char()
    summary = fields.Text()
    ##########################################################################

    def _get_recording(self):
        for rec in self:
            rec.recording = rec.recording_data if rec.recording_data else rec.recording_attachment

    def _get_transcript_short(self):
        for rec in self:
            if rec.transcript:
                rec.transcript_short = rec.transcript
            else:
                rec.transcript_short = ''

    @api.model
    def create(self, vals):
        rec = super(Recording, self.with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True)).create(vals)
        # Commit to the database as recordings are created by the Agent.
        if self.env['asterisk_plus.settings'].sudo().get_param('transcript_calls'):
            rec.get_transcript(fail_silently=True)
        return rec

    def write(self, vals):
        if vals.get("tags"):
            # Get tags to be notified when attached to recording
            present_tags = self.tags.ids
            new_tags = vals.get("tags")
            if release.version_info[0] < 17:
                tags_to_notify = set(new_tags[0][2]) - set(present_tags)
            else:
                tags_to_notify = set([k[1] for k in new_tags]) - set(present_tags)
            msg = "Tag attached to recording {}".format(self.uniqueid)
            for tag in tags_to_notify:
                self.env['asterisk_plus.tag'].browse(
                    tag).sudo().message_post(
                        subject=_('Tag attached to recording'),
                        body=msg)
        res = super(Recording, self).write(vals)

    def unlink(self):
        # Currently remote unlinking with many records is slow.
        # So we disable it until we find a solution for bulk deletion.
        return super(Recording, self).unlink()
        #
        for rec in self:
            if not any([rec.recording_data, rec.recording_attachment]) and self.env.context.get('no_remote_delete') == True:
                # Send remove command to the Agent and skip removal if Agent is not accessible
                rec.call.server.local_job(
                    fun='file.delete',
                    args=rec.file_path,
                    raise_exc=False,
                    res_model='asterisk_plus.recording',
                    res_method='file_delete_result',
                    pass_back={'rec_id': rec.id},
                )
                # That's all, recording will be removed only after agent removes it.
            else:
                super(Recording, rec).unlink()
        return True

    @api.model
    def file_delete_result(self, result, rec_id=None):
        if result == True:
            # We use sudo as the Agent does not have access to remove recordings, so write access.
            if self.check_access_rights('write', raise_exception=False):
                self.env['asterisk_plus.recording'].sudo().with_context(
                    no_remote_delete=True).browse(rec_id).unlink()
        return True

    def _get_recording_widget(self):
        for rec in self:
            try:
                recording_source = 'recording_data' if rec.recording_data else 'recording_attachment'
                if rec.recording_data or rec.recording_attachment:
                    # Odoo stored recording, create a local URL.
                    rec.recording_widget = '<audio id="sound_file" preload="auto" ' \
                        'controls="controls"> ' \
                        '<source src="/web/content?model=asterisk_plus.recording&' \
                        'id={recording_id}&filename={filename}&field={source}&' \
                        'filename_field=recording_filename&download=True" />' \
                        '</audio>'.format(
                            recording_id=rec.id,
                            filename=rec.recording_filename,
                            source=recording_source)
                else:
                    # Remotely stored recording, create a link to the remote URL
                    recording_url = urljoin(rec.recording_access_url, quote(rec.file_path))
                    rec.recording_widget = '<audio id="sound_file" preload="auto" ' \
                        'controls="controls"><source src="{}"/></audio>'.format(recording_url)
            except Exception as e:
                logger.exception('Recording widget error:')
                rec.recording_widget = ''

    @api.model
    def save_call_recordings(self, call):
        if call.duration == 0:
            debug(self, 'Skip save recording, call duration 0.')
            return False
        recording_channel_data = self.env['asterisk_plus.channel_data'].search(
            [('call', '=', call.id), ('key', '=', 'recording_file_path')])
        if not recording_channel_data:
            debug(self, 'Recording file not specified for call id: {}'.format(call.id))
            return False
        for rec in recording_channel_data:
            self.save_call_recording(call, rec)

    @api.model
    def save_call_recording(self, call, recording_channel_data):
        recording_file_path = recording_channel_data.value
        debug(self, 'Call %s getting recording from %s' % (
            call.id, recording_file_path))
        # Get recording access settings.
        kwargs = {
            'recordings_access': self.env['asterisk_plus.settings'].sudo().get_param('recordings_access'),
            'recordings_access_url': self.env['asterisk_plus.settings'].sudo().get_param('recordings_access_url'),
            'recordings_s3_region': self.env['asterisk_plus.settings'].sudo().get_param('recordings_s3_region'),
            'recordings_s3_bucket': self.env['asterisk_plus.settings'].sudo().get_param('recordings_s3_bucket'),
            'recordings_s3_key': self.env['asterisk_plus.settings'].sudo().get_param('recordings_s3_key'),
            'recordings_s3_secret': self.env['asterisk_plus.settings'].sudo().get_param('recordings_s3_secret'),
        }
        mp3_encode = self.env['asterisk_plus.settings'].sudo().get_param(
            'use_mp3_encoder')
        if mp3_encode:
            kwargs['file_format'] = 'mp3'
            kwargs['mp3_bitrate'] = int(self.env['asterisk_plus.settings'].sudo().get_param(
                'mp3_encoder_bitrate', default='96'))
            kwargs['mp3_quality'] = int(self.env['asterisk_plus.settings'].sudo().get_param(
                'mp3_encoder_quality', default=4))
        call.server.local_job(
            fun='recording.get_file',
            args=recording_file_path,
            kwargs=kwargs,
            res_model='asterisk_plus.recording',
            res_method='upload_recording',
            pass_back={'call_id': call.id, 'file_path': recording_file_path},
            raise_exc=False,
        )
        return True

    @api.model
    def upload_recording(self, data, call_id=None, file_path=None):
        """Upload call recording to Odoo."""
        if data == False:
            debug(self, 'No recording {} to upload for call {}'.format(file_path, call_id))
            return False
        if not isinstance(data, dict):
            debug(self, 'Upload recording error: {}'.format(data))
            return False
        if data.get('error'):
            logger.error('Cannot get call recoding: %s', data['error'])
            return False
        file_data = data.get('file_data')
        file_name = data.get('file_name')
        call = self.env['asterisk_plus.call'].browse(call_id)
        debug(self, 'Call recording upload for call {}'.format(call.id))
        vals = {
            'uniqueid': call.uniqueid,
            'recording_filename': data['file_name'],
            'recording_access': data.get('recording_access'),
            'recording_access_url': data.get('recording_access_url'),
            'call': call.id,
            'partner': call.partner.id,
            'calling_user': call.calling_user.id,
            'answered_user': call.answered_user.id,
            'calling_number': call.calling_number,
            'called_number': call.called_number,
            'answered': call.answered,
            # Accept file path manipulation by the Agent (when MP3 conversion and http link).
            'file_path': data.get('file_path', file_path),
        }
        if self.env['asterisk_plus.settings'].sudo().get_param(
                'recording_storage') == 'filestore':
            vals['recording_attachment'] = file_data
        else:
            vals['recording_data'] = file_data
        # Create a recording
        rec = self.create(vals)
        # Remove recording after download
        if self.env['asterisk_plus.settings'].sudo().get_param('recordings_access') in [
                    'local', 'asterisk_http'] and \
                self.env['asterisk_plus.settings'].sudo().get_param('recording_remove_after_download'):
            call.server.local_job(
                fun='file.delete',
                args=file_path,
                raise_exc=False,
            )
        return True

    @api.model
    def delete_recordings(self):
        """Cron job to delete calls recordings.
        """
        days = self.env[
            'asterisk_plus.settings'].get_param('recordings_keep_days')
        expire_date = datetime.utcnow() - timedelta(days=int(days))
        expired_recordings = self.env['asterisk_plus.recording'].search([
            ('keep_forever', '=', 'no'),
            ('answered', '<=', expire_date.strftime('%Y-%m-%d %H:%M:%S'))
        ])
        logger.info('Expired {} recordings'.format(len(expired_recordings)))
        expired_recordings.unlink()

    @api.model
    def update_mvm_filename(self, event):
        """AMI VarSet event for MinivmRecord app.
        """
        filename = event['Value']
        uniqueid = event['Uniqueid']
        self.env['asterisk_plus.channel_data'].create({
            'uniqueid': uniqueid,
            'key': 'minivm_filename',
            'value': filename,
        })
        return True

    @api.model
    def update_mvm_duration(self, event):
        """AMI VarSet event for MinivmRecord app.
        """
        uniqueid = event['Uniqueid']
        channel_data = self.env['asterisk_plus.channel_data'].search([
            ('uniqueid', '=', uniqueid),
            ('key', '=', 'minivm_filename')])
        if channel_data:
            filename = '{}.WAV'.format(channel_data[0].value)
            debug(self, 'Found MINIVM_FILENAME {}'.format(filename))
            channel = self.env['asterisk_plus.channel'].search([('uniqueid', '=', uniqueid)])
            if not channel:
                logger.warning('Channel not found by uniquid %s, cannot upload VoiceMail.', uniqueid)
                return False
            kwargs = {}
            server = channel.server
            mp3_encode = self.env['asterisk_plus.settings'].sudo().get_param(
                'use_mp3_encoder')
            if mp3_encode:
                kwargs['file_format'] = 'mp3'
                kwargs['mp3_bitrate'] = self.env['asterisk_plus.settings'].sudo().get_param(
                    'mp3_encoder_bitrate', default='96')
                kwargs['mp3_quality'] = int(self.env['asterisk_plus.settings'].sudo().get_param(
                    'mp3_encoder_quality', default=4))
            server.local_job(
                fun='recording.get_file',
                args=filename,
                kwargs=kwargs,
                res_model='asterisk_plus.recording',
                res_method='upload_voicemail',
                pass_back={'channel_id': channel.id, 'file_path': filename},
                raise_exc=False,
            )
            return True
        else:
            logger.warning('Could not get MINIVM_FILENAME from channel data!')
            return False

    @api.model
    def upload_voicemail(self, data, channel_id=None, file_path=None):
        """Upload voicemail to Odoo."""
        if data == False:
            debug(self, 'No voicemail {} to upload for channel {}'.format(file_path, channel_id))
            return False
        if not isinstance(data, dict):
            debug(self, 'Upload voicemail error: {}'.format(data))
            return False
        if data.get('error'):
            logger.error('Cannot get voicemail: %s', data['error'])
            return False
        file_data = data.get('file_data')
        file_name = data.get('file_name')
        channel = self.env['asterisk_plus.channel'].browse(channel_id)
        if channel and channel.call:
            debug(self, 'Voicemail upload for channel {}'.format(channel.channel))
            vals = {
                'voicemail_filename': data['file_name'],
                'voicemail_data': file_data
            }
            channel.call.write(vals)
            return True
        else:
            debug(self, 'No call for channel {} to upload voicemail.'.format(channel.id))
            return False

    def _get_icon(self):
        for rec in self:
            if rec.keep_forever == 'yes':
                rec.icon = '<span class="fa fa-floppy-o"></span>'
            else:
                rec.icon = ''

    def prepare_transcription_content(self):
        data = {
            'file_name': self.recording_filename,
            'content': self.recording.decode(),
        }
        return data

    ############## TRANSCRIPTION METHODS #####################################

    def get_transcript(self, fail_silently=False):
        self.ensure_one()
        # First check if the call matches the transcription rules.
        if fail_silently and not self.env['asterisk_plus.transcription_rule'].sudo().check_rules(
                self.calling_number, self.called_number):
            return False
        # We passed the rules, let's do the transcription!
        url = urljoin(self.env['%s.settings' % MODULE_NAME].sudo().get_param('api_url'),
            'transcription')
        self.transcription_token = str(uuid.uuid4())
        self.env.cr.commit()
        try:
            data = self.prepare_transcription_content()
            data.update({
                'summary_prompt': self.env['%s.settings' % MODULE_NAME].sudo().get_param('summary_prompt'),
                'callback_url': urljoin(
                    self.env['asterisk_plus.settings'].sudo().get_param('web_base_url'),
                    '/{}/transcript/{}'.format(MODULE_NAME, self.id)),
            'transcription_token': self.transcription_token,
            'notify_uid': self.env.user.id,
            })
            res = requests.post(url,
                json=data,
                headers={
                    'x-instance-uid': self.env['%s.settings' % MODULE_NAME].sudo().get_param('instance_uid'),
                    'x-api-key': self.env['ir.config_parameter'].sudo().get_param('odoopbx.api_key')
                })
            if not res.ok:
                self.transcription_error = res.text
                if not fail_silently:
                    raise ValidationError(res.text)
            logger.info('Transcription request has been sent')
        except Exception as e:
            logger.exception('Transcription error: %s', e)
            if not fail_silently:
                raise ValidationError('Transcription error: %s' % e)

    def update_transcript(self, data):
        # Update transcription and also erase access token.
        self.ensure_one()
        transcription_price = data.get('transcription_price')
        if transcription_price:
            # Round
            transcription_price = round(transcription_price, 4)
        vals = {
            'transcript': data.get('transcript'),
            'transcription_price': str(transcription_price),
            'summary': data.get('summary'),
            # Reset the token
            'transcription_token': False,
            'transcription_error': data.get('transcription_error')
        }
        self.write(vals)
        # Reload views when transcription has come.
        self.env['%s.settings' % MODULE_NAME].odoopbx_reload_view('%.recording' % MODULE_NAME)
        # Notify user
        if data.get('notify_uid'):
            self.env['%s.settings' % MODULE_NAME].odoopbx_notify(
                'Transcription updated', notify_uid=data['notify_uid'])
            self.env['%s.settings' % MODULE_NAME].odoopbx_reload_view('%s.recording' % MODULE_NAME)
        # Register summary if partner is linked.
        if self.partner and data.get('summary') and self.env[
                '%s.settings' % MODULE_NAME].sudo().get_param('register_summary'):
            obj = self.partner
            try:
                if release.version_info[0] < 14:
                    obj.sudo(SUPERUSER_ID).message_post(body=data['summary'])
                else:
                    obj.with_user(SUPERUSER_ID).message_post(body=data['summary'])
                # Reload the view of res.partner
                self.env['%s.settings' % MODULE_NAME].odoopbx_reload_view('res.partner')
            except Exception as e:
                logger.error('Cannot register summary: %s', e)

##########  END OF TRANSCRIPTION METHODS #########################################################
