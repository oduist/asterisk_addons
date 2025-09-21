# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2023

from odoo import models, fields, api
from odoo.addons.asterisk_plus.models.settings import debug

class MulticompanyCall(models.Model):
    _inherit = 'asterisk_plus.call'
    company_id = fields.Many2one('res.company', compute='_set_company',
        ondelete='set null', store=True)

    @api.depends('calling_user', 'answered_user', 'partner', 'ref')
    def _set_company(self):
        for rec in self:
            # do nothing if company_id is already set
            if rec.company_id:
                return
            for i in 'calling_user', 'answered_user', 'partner', 'ref':
                value = getattr(rec, i, None)
                if value and value.company_id:
                    rec.company_id = value.company_id
                    break
