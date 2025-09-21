# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2021
from odoo import models, fields


class AccountCall(models.Model):
    _name = 'asterisk_plus.call'
    _inherit = 'asterisk_plus.call'

    ref = fields.Reference(selection_add=[
        ('account.move', 'Invoicing')])

    def update_reference(self, **kwargs):
        res = super(AccountCall, self).update_reference(**kwargs)
        if not res:
            if self.partner:
                account_move = self.env['account.move'].sudo().search(
                    [
                        ('partner_id', '=', self.partner.id),
                        ('state', '=', 'posted'),
                        ('type', 'in', ['out_invoice', 'in_invoice']),
                        ('invoice_payment_state', '!=', 'paid'),
                    ], limit=1)
                if account_move:
                    self.sudo().ref = account_move
                    return True
