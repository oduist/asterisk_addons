# -*- coding: utf-8 -*

import logging
from odoo import api, models, fields
from odoo.addons.asterisk_plus.models.license import ODUIST_MODULES

ODUIST_MODULES.append('asterisk_plus_account')

logger = logging.getLogger(__name__)


class AccountOrder(models.Model):
    _name = 'account.move'
    _inherit = 'account.move'

    asterisk_calls_count = fields.Integer(
        compute='_get_asterisk_calls_count', string='Calls', compute_sudo=True)
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    def _get_asterisk_calls_count(self):
        for rec in self:
            rec.asterisk_calls_count = self.env[
                'asterisk_plus.call'].search_count([
                    ('res_id', '=', rec.id),
                    ('model', '=', 'account.move')])
