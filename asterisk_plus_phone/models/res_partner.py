# -*- coding: utf-8 -*
from odoo import api, models


class Partner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        res = super(Partner, self).create(vals_list)
        if self.env.context.get('call_id'):
            call = self.env['asterisk_plus.call'].browse(self.env.context['call_id'])
            call.partner = res.id
        return res
