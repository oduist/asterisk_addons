# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2020
from odoo import models, fields, api, _


class Event(models.Model):
    _name = 'asterisk_plus.event'
    _description = 'Asterisk Events'

    source = fields.Selection([
        ('AMI', 'AMI'),
        ('FAGI', 'FAGI'),
        ('ARI', 'ARI')],
        required=True)
    name = fields.Char(required=True)
    model = fields.Char(required=True)
    method = fields.Char(required=True)
    delay = fields.Float(default=0, required=True)
    is_enabled = fields.Boolean(default=True, string='Enabled')
    condition = fields.Text()
    update = fields.Selection([
            ('no', 'Not Updateable'),
            ('yes', 'Updateable'),
        ], default='yes')

    icon = fields.Html(compute='_get_icon', string='I')

    _sql_constraints = [
        ('event_uniq',
         'check(1=1)',
         _('Should be remove in next pre-upgrade script.'))
    ]

    def _get_icon(self):
        for rec in self:
            if rec.update == 'yes':
                rec.icon = '<span class="fa fa-unlock"></span>'
            else:
                rec.icon = '<span class="fa fa-lock"></span>'

    def write(self, vals):
        # Prevent record update if update = 'no'. If statement hack to allow overwrite update value
        for rec in self:
            if rec.update == 'no' and vals.get('update', 'no') == 'no':
                self.pop(rec)
        return super(Event, self).write(vals)
