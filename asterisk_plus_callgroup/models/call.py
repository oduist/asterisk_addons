# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2021
from datetime import datetime, timedelta
import logging
import pytz
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.asterisk_plus.models.settings import debug

logger = logging.getLogger(__name__)


class Call(models.Model):
    _inherit = 'asterisk_plus.call'
    
    callgroup = fields.Many2one('asterisk_plus.callgroup', ondelete='set null')    


    @api.constrains('is_active')
    def register_call(self):
        res = super().register_call()
        try:
            if self.direction == 'in' and self.status != 'answer':
                self.callgroup_missed_call_activity()
        except Exception:
            logger.exception('Register callgroup error:')
        return res

    def callgroup_missed_call_activity(self):
        # Get callgroup from the channel data
        ch_data = self.env['asterisk_plus.channel_data'].search(
            [('uniqueid', '=', self.uniqueid), ('key', '=', 'callgroup_id')],
            limit=1)
        if not ch_data:
            return
        callgroup = self.env['asterisk_plus.callgroup'].search(
            [('id', '=', int(ch_data.value))])
        if not callgroup.dispatcher:
            debug(self, 'Not creating activities for missed call.')
            return
        self.callgroup_create_user_activity(callgroup)

    def callgroup_create_user_activity(self, callgroup):
        debug(self, 'Creating missed call activity for user %s and callgroup %s' % (callgroup.dispatcher.name, callgroup.name))
        activity_vals = {
            'activity_type_id': self.env.ref('mail.mail_activity_data_call').id,
            'note': 'Follow up on customer request',
            'summary': 'Missed call from {}'.format(self.partner.name or self.calling_number),
            'res_id': self.id,
            'res_model_id': self.env['ir.model']._get('asterisk_plus.call').id,
            'user_id': callgroup.dispatcher.id,
            'date_deadline': fields.Date.today(),
        }
        self.env['mail.activity'].sudo().create(activity_vals)
