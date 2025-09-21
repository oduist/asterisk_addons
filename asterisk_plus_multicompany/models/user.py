# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2023
from odoo import models, fields

class MulticompanyPbxUser(models.Model):
    _inherit = 'asterisk_plus.user'
    company_id = fields.Many2one(related='user.company_id', store=True)
