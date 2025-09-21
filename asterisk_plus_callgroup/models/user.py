# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2021
from datetime import datetime, timedelta
import logging
import pytz
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.asterisk_plus.models.settings import debug

logger = logging.getLogger(__name__)


class User(models.Model):
    _inherit = 'asterisk_plus.user'

    callgroup_on_unavail = fields.Many2one(
        comodel_name='asterisk_plus.callgroup',
        string='CallGroup on Unavailable',
        help='Forward the caller to the specified call group when user did not answer the call',
        ondelete='set null')

    @api.model
    def fagi_request(self, request):
        res = super().fagi_request(request)
        if res:
            # Find the user
            extension = request['agi_extension']
            users = self.env['asterisk_plus.user'].search(
                ['|', ('did_number', '=', extension), ('exten', '=', extension)])
            if len(users) == 1:
                user = users[0]
                if user.callgroup_on_unavail:
                    debug(self, 'CallGroup on unavailable set for user {}.'.format(user.name))
                    res.append('EXEC VERBOSE "*** User has call group on unailable set to %s ***"' % user.callgroup_on_unavail.name)
                    res.append('EXEC GOTO {},{},1'.format(
                        request['agi_context'], user.callgroup_on_unavail.internal_phone))
            elif len(users) > 1:
                debug(self, 'Multiple users found by number, not using Call Group on Unavailable.')
        return res
