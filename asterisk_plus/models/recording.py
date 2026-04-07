import io
from datetime import datetime, timedelta
import requests
import sys
import time
from urllib.parse import urljoin, quote
import uuid
import logging
from odoo import models, fields, api, tools, release, release, SUPERUSER_ID
from odoo.exceptions import ValidationError
from .server import debug
from .settings import RECORDING_ACCESS_SELECTION

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
        recording_widget = fields.Html(compute='_get_recording_widget', sanitize=False)
    else:
        recording_widget = fields.Char(compute='_get_recording_widget')
    recording_filename = fields.Char(readonly=True, index=True)
    recording_data = fields.Binary(attachment=False, readonly=True)
    recording = fields.Binary(compute='_get_recording')
    recording_attachment = fields.Binary(attachment=True, readonly=True)
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
    transcript = fields.Text(readonly=True)
    transcribe_error = fields.Char(readonly=True)
    transcription_completion_tokens = fields.Char(string='Completion Tokens', readonly=True)
    transcription_completion_model = fields.Char(string='Model', readonly=True)
    transcription_prompt_tokens = fields.Char(string='Prompt Tokens', readonly=True)
    transcription_prompt = fields.Char(string='Prompt', readonly=True)
    transcription_finish_reason = fields.Char(string='Finish Reason', readonly=True)
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

    @api.model_create_multi
    def create(self, vals_list):
        res = super(Recording, self.with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True)).create(vals_list)
        return res

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
                        subject='Tag attached to recording',
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
            have_access = self.check_access_rights('write', raise_exception=False) if release.version_info[0] < 18 else self.check_access('write')
            if have_access:
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

    def get_all_recording_data(self, call):
        settings = self.env['asterisk_plus.settings'].sudo()
        kwargs = {
            'recordings_access': settings.get_param('recordings_access'),
            'recordings_access_url': settings.get_param('recordings_access_url'),
            'recordings_s3_region': settings.get_param('recordings_s3_region'),
            'recordings_s3_bucket': settings.get_param('recordings_s3_bucket'),
            'recordings_s3_key': settings.get_param('recordings_s3_key'),
            'recordings_s3_secret': settings.get_param('recordings_s3_secret'),
        }
        if settings.get_param('use_mp3_encoder'):
            kwargs['file_format'] = 'mp3'
            kwargs['mp3_bitrate'] = int(settings.get_param(
                'mp3_encoder_bitrate', default='96'))
            kwargs['mp3_quality'] = int(settings.get_param(
                'mp3_encoder_quality', default=4))
        return kwargs

    @api.model
    def save_call_recording(self, call, recording_channel_data):
        recording_file_path = recording_channel_data.value
        debug(self, 'Call %s getting recording from %s' % (
            call.id, recording_file_path))
        # Get recording access settings.
        kwargs = self.get_all_recording_data(call)
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
        if self.env['asterisk_plus.settings'].sudo().get_param('transcribe_calls'):
            rec.get_transcript(fail_silently=True)
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

    ############## TRANSCRIPTION METHODS #####################################

    def get_transcript(self, fail_silently=False):
        self.ensure_one()
        # Check transcription rules before processing.
        if fail_silently and not self.env[
                'asterisk_plus.transcription_rule'].sudo().check_rules(
                self.calling_number, self.called_number):
            return False
        openai_api_key = self.env['asterisk_plus.settings'].sudo().get_param('openai_api_key')
        if not openai_api_key:
            if fail_silently:
                logger.warning('OpenAI key is not set! Not doing call transcription.')
                return
            else:
                raise ValidationError('OpenAI API key is not set!')
        # We passed the rules, let's do the transcription!
        try:
            data = {
                'openai_api_key': openai_api_key,
                'summary_prompt': self.env['asterisk_plus.settings'].sudo().get_param('summary_prompt'),
                'completion_model': self.env['asterisk_plus.settings'].sudo().get_param('completion_model'),
            }
            self.call.server.local_job(
                fun='recording.get_transcript',
                args=self.file_path,
                kwargs=data,
                res_model='asterisk_plus.recording',
                res_method='update_transcript',
                pass_back={'rec_id': self.id, 'notify_uid': self.env.user.id},
                raise_exc=False,
            )
            return True
            logger.info('Transcription request has been sent.')
        except Exception as e:
            logger.exception('Transcription error: %s', e)
            if not fail_silently:
                raise ValidationError('Transcription error: %s' % e)
    @api.model
    def update_transcript(self, data, rec_id=None, notify_uid=None):
        rec = self.browse(rec_id)
        vals = {
            'transcript': data.get('transcript'),
            'summary': data.get('summary'),
            'transcribe_error': data.get('error'),
            'transcription_prompt': data.get('prompt'),
            'transcription_finish_reason': data.get('finish_reason'),
            'transcription_prompt_tokens': data.get('prompt_tokens'),
            'transcription_completion_tokens': data.get('completion_tokens'),
            'transcription_completion_model': data.get('completion_model'),
        }
        rec.write(vals)
        # Reload views when transcription has come.
        self.env['asterisk_plus.settings'].asterisk_plus_reload_view('asterisk_plus.recording')
        # Notify user
        if notify_uid:
            self.env['asterisk_plus.settings'].asterisk_plus_notify(
                'Transcription updated', notify_uid=notify_uid)
            self.env['asterisk_plus.settings'].asterisk_plus_reload_view('asterisk_plus.recording')
        # Register summary if partner is linked.
        register_summary = self.env['asterisk_plus.settings'].sudo().get_param('register_summary')
        if rec.partner and data.get('summary') and register_summary:
            obj = rec.partner
            try:
                if release.version_info[0] < 14:
                    obj.sudo(SUPERUSER_ID).message_post(body=data['summary'])
                else:
                    obj.with_user(SUPERUSER_ID).message_post(body=data['summary'])
                # Reload the view of res.partner
                self.env['asterisk_plus.settings'].asterisk_plus_reload_view('res.partner')
            except Exception as e:
                logger.error('Cannot register summary: %s', e)
        # Register summary if reference is linked.
        if rec.call.ref and not rec.call.model == 'res.partner' and data.get('summary') and register_summary:
            obj = rec.call.ref
            try:
                if release.version_info[0] < 14:
                    obj.sudo(SUPERUSER_ID).message_post(body=data['summary'])
                else:
                    obj.with_user(SUPERUSER_ID).message_post(body=data['summary'])
                # Reload the view of res.partner
                self.env['asterisk_plus.settings'].asterisk_plus_reload_view(rec.call.model)
            except Exception as e:
                logger.error('Cannot register summary: %s', e)

        return True

##########  END OF TRANSCRIPTION METHODS #########################################################
