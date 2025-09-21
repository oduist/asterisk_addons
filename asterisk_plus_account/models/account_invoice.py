# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2021
import logging
from odoo import api, models, fields, _

logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    asterisk_calls_count = fields.Integer(
        compute='_get_asterisk_calls_count', string=_('Calls'), compute_sudo=True)
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    def _get_asterisk_calls_count(self):
        for rec in self:
            rec.asterisk_calls_count = self.env[
                'asterisk_plus.call'].search_count([
                    ('res_id', '=', rec.id),
                    ('model', '=', 'account.move')])
