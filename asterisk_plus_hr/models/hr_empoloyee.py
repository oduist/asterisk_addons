# -*- coding: utf-8 -*

from odoo import api, models, fields
from odoo.addons.asterisk_plus.models.license import ODUIST_MODULES

ODUIST_MODULES.append('asterisk_plus_hr')


class HrEmployeePrivate(models.Model):
    _name = 'hr.employee'
    _inherit = 'hr.employee'

    asterisk_calls_count = fields.Integer(
        compute='_get_asterisk_calls_count', string='Calls', compute_sudo=True)

    def _get_asterisk_calls_count(self):
        for rec in self:
            rec.asterisk_calls_count = self.env[
                'asterisk_plus.call'].search_count([
                    ('res_id', '=', rec.id),
                    ('model', '=', 'hr.employee')])
