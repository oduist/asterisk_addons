import base64
import requests
from requests.compat import urljoin
from odoo import fields, models, api
from odoo.addons.asterisk_plus.models.settings import debug


class YeastarRecording(models.Model):
    _inherit = 'asterisk_plus.recording'

    @api.model
    def on_yeastar_cdr(self, event):
        # debug(self, 'Yeastar Cdr event: {}'.format(event))
        recording = event.get('Recordfile')
        if not recording:
            debug(self, 'Yeastar: Call Recoring not set.')
            return False
        debug(self, 'Getting recording from Yeastar: %s', recording)
        return self.save_recording_yeastar(event)

    def save_recording_yeastar(self, event):
        recording = event.get('Recordfile')      
        server = self.env.ref('asterisk_plus.default_server')
        return getattr(self, 'save_recording_yeastar_{}'.format(server.yeastar_model))(event)

    def save_recording_yeastar_p_se(self, event):
        data = server.yeastar_api_request('recording/download', method='get',
            data={'file': recording})
        download_url = '{}?access_token={}'.format(data['download_resource_url'],
             server.yeastar_access_token)
        url = urljoin(server.yeastar_api_url, download_url)
        resp = requests.get(url)
        channel = self.env['asterisk_plus.channel'].search([('uniqueid', '=', event.get('UniqueID'))], limit=1)
        self.upload_recording({
            'file_data': base64.b64encode(resp.content).decode(),
            'file_name': recording,            
        }, channel_id=channel.id)        
        return True

    def save_recording_yeastar_s(self, event):
        recording = event.get('Recordfile')      
        server = self.env.ref('asterisk_plus.default_server')
        random_data = server.yeastar_api_request('recording/get_random', method='post',
            data={'recording': recording})
        resp = server.yeastar_api_request('recording/download', method='get', data={
            'recording': recording, 'random': random_data['random']
        }, return_json=False)
        channel = self.env['asterisk_plus.channel'].search([('uniqueid', '=', event.get('UniqueID'))], limit=1)
        self.upload_recording({
            'file_data': base64.b64encode(resp.content).decode(),
            'file_name': recording,            
        }, channel_id=channel.id)        
        return True

