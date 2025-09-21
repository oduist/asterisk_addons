import base64
import re
import requests
from requests.compat import urljoin
from odoo import fields, models, api
from odoo.addons.asterisk_plus.models.settings import debug


RE_GS_MIXMONITOR_FILENAME = re.compile(r'(auto-\d+-\d+-\d+\.wav)')


class gsRecording(models.Model):
    _inherit = 'asterisk_plus.recording'

    @api.model
    def on_gs_new_exten_mixmonitor_filename(self, event):
        debug(self, 'GS New event MixMonitor: {}'.format(event))
        found = RE_GS_MIXMONITOR_FILENAME.search(event.get('AppData', ''))
        if not found:
            logger.error(
                'Cannot extract MixMonitor filename from the AppData: %s', event.get('AppData'))
            return False
        filename = found.group(1)
        # Inject it as a normal SetVar even
        event.update({
            'Variable': 'MIXMONITOR_FILENAME',
            'Value': filename,
        })
        return self.env['asterisk_plus.channel'].update_recording_filename(event)
        
    @api.model
    def save_call_recording(self, call, recording_channel_data):
        recording_file_path = recording_channel_data.value
        debug(self, 'Call %s getting recording from %s' % (
            call.id, recording_file_path))        
        server = self.env.ref('asterisk_plus.default_server')
        file_content = server.gs_api_request('recapi', data={
            'filedir': 'monitor',
            'filename': recording_file_path,
        }, return_json=False)
        channel = self.env['asterisk_plus.channel'].search([('uniqueid', '=', call.uniqueid)], limit=1)
        self.upload_recording({
            'file_data': base64.b64encode(file_content).decode(),
            'file_name': 'recording_%s.wav' % call.id,
        }, call_id=call.id)
        return True
