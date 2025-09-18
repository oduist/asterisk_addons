import logging
from odoo import api, models, fields, release

logger = logging.getLogger(__name__)


class Task(models.Model):
    _name = 'project.task'
    _inherit = 'project.task'

    asterisk_calls_count = fields.Integer(compute='_get_asterisk_calls_count', string='Calls')
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')
    recorded_calls = fields.One2many(
        'asterisk_plus.recording', 'task')

    def _get_asterisk_calls_count(self):
        for rec in self:
            rec.asterisk_calls_count = self.env[
                'asterisk_plus.call'].search_count(
                    [('res_id', '=', rec.id), ('model', '=', 'project.task')])

    @api.model_create_multi
    def create(self, vals_list):
        recs = super(Task, self).create(vals_list)
        for rec in recs:
            try:
                if self.env.context.get('call_id'):
                    call = self.env['asterisk_plus.call'].browse(
                        self.env.context['call_id'])
                    call.write({
                        'res_id': rec.id,
                        'model': 'project.task'})
            except Exception as e:
                logger.exception(e)
        if recs:
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return recs
