# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseConfirmWizard(models.TransientModel):
    _name = 'asterisk_plus.purchase_confirm'
    _description = 'Purchase Confirmation'

    payment_link = fields.Char(readonly=True)
    subtotal = fields.Float(readonly=True)
    discount_label = fields.Char(readonly=True)
    discount_amount = fields.Float(readonly=True)
    total = fields.Float(readonly=True)
    has_discount = fields.Boolean(readonly=True)

    def action_proceed(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.payment_link,
            'target': 'new',
        }
