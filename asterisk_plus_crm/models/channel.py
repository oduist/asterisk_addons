# -*- coding: utf-8 -*

import logging
from odoo import models, fields, api, release
from odoo.exceptions import ValidationError
from odoo.addons.asterisk_plus.models.settings import debug


logger = logging.getLogger(__name__)


class CrmChannel(models.Model):
    _inherit = 'asterisk_plus.channel'

    @api.model
    def on_ami_hangup(self, event):
        self.check_access_rights('create', raise_exception=True) if release.version_info[0] < 18 else self.check_access('create')
        ret = super().on_ami_hangup(event)
        if not ret[0]:
            return ret
        channel = self.env['asterisk_plus.channel'].browse(ret[0])
        if channel.call and channel.uniqueid == channel.linkedid:
            try:
                channel.call.sudo()._auto_create_lead()
            except Exception:
                logger.exception('Lead autocreate exception on Hangup for {}'.format(
                    channel.call))
        return ret
