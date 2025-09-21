# -*- coding: utf-8 -*-
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2021
from odoo import models, fields, api, _


class Tag(models.Model):
    _name = 'asterisk_plus.tag'
    _inherit = 'mail.thread'
    _description = 'Recording Tag'

    name = fields.Char(required=True)
    recordings = fields.Many2many('asterisk_plus.recording',
                                  relation='asterisk_plus_recording_tag',
                                  column1='recording', column2='tag')
    recording_count = fields.Integer(compute='_get_recording_count',
                                string=_('Recordings'))

    _sql_constraints = [
        ('name_uniq', 'unique (name)', _('The name must be unique!')),
    ]

    @api.model
    def create(self, vals):
        res = super(Tag, self).create(vals)
        return res

    def _get_recording_count(self):
        for rec in self:
            rec.recording_count = self.env['asterisk_plus.recording'].search_count(
                    [('tags', 'in', rec.id)])
