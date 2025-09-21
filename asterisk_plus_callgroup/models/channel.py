# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2023
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.addons.asterisk_plus.models.settings import debug


logger = logging.getLogger(__name__)


class CallgroupChannel(models.Model):
    _inherit = 'asterisk_plus.channel'

    @api.model
    def on_ami_hangup(self, event):
        ret = super().on_ami_hangup(event)
        if not ret[0]:
            return ret
        channel = self.env['asterisk_plus.channel'].browse(ret[0])
        if channel.call:
            # Find a callgroup.
            ch_data = self.env['asterisk_plus.channel_data'].search(
                [('uniqueid', '=', channel.uniqueid), ('key', '=', 'callgroup_id')],
                limit=1)
            if ch_data:
                channel.call.callgroup = int(ch_data[0].value)
        return ret
