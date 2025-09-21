# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2021
from odoo import models, fields


class SaleCall(models.Model):
    _name = 'asterisk_plus.call'
    _inherit = 'asterisk_plus.call'

    ref = fields.Reference(selection_add=[
        ('sale.order', 'Sales')])

    def update_reference(self, **kwargs):
        res = super(SaleCall, self).update_reference(**kwargs)
        if not res:
            if self.partner:
                sale_order = self.env['sale.order'].search([
                    ('partner_id', '=', self.partner.id)], limit=1)
                if sale_order:
                    self.ref = sale_order
                    return True
