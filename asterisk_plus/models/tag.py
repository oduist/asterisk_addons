# -*- coding: utf-8 -*-

from odoo import models, fields, api, release


class Tag(models.Model):
    _name = 'asterisk_plus.tag'
    _inherit = 'mail.thread'
    _description = 'Recording Tag'

    name = fields.Char(required=True)
    recordings = fields.Many2many('asterisk_plus.recording',
                                  relation='asterisk_plus_recording_tag',
                                  column1='recording', column2='tag')
    recording_count = fields.Integer(compute='_get_recording_count')

    if release.version_info[0] >= 19:
        _name_uniq = models.Constraint('UNIQUE(name)', 'The name must be unique!')
    else:
        _sql_constraints = [
            ('name_uniq', 'unique (name)', 'The name must be unique!'),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        res = super(Tag, self).create(vals_list)
        return res

    def _get_recording_count(self):
        for rec in self:
            rec.recording_count = self.env['asterisk_plus.recording'].search_count(
                    [('tags', 'in', rec.id)])
