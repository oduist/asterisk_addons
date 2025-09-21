# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2021
from odoo import models, fields


class HrCall(models.Model):
    _inherit = 'asterisk_plus.call'

    ref = fields.Reference(selection_add=[
        ('hr.employee', 'Employee'),
    ])
