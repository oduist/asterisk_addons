# -*- coding: utf-8 -*

from odoo import models, fields


class HrCall(models.Model):
    _inherit = 'asterisk_plus.call'

    ref = fields.Reference(selection_add=[
        ('hr.employee', 'Employee'),
        ('hr.employee.public', 'Employee Public'),
    ])
