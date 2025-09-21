# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2021
import logging
from odoo import api, models, fields, tools, release, _

logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    asterisk_calls_count = fields.Integer(
        compute='_get_asterisk_calls_count', string=_('Calls'), compute_sudo=True)
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    def _get_asterisk_calls_count(self):
        for rec in self:
            rec.asterisk_calls_count = self.env[
                'asterisk_plus.call'].search_count([
                    ('res_id', '=', rec.id),
                    ('model', '=', 'sale.order')])

    @api.model
    def create(self, vals):
        try:
            if self.env.context.get('call_id'):
                call = self.env['asterisk_plus.call'].browse(
                    self.env.context['call_id'])
                if call.partner:
                    vals['partner_id'] = call.partner.id
        except Exception as e:
            logger.exception(e)
        res = super(SaleOrder, self).create(vals)
        if res:
            if release.version_info[0] >= 17:
                self.invalidate_model(flush=True)
            else:
                self.clear_caches()
        return res
