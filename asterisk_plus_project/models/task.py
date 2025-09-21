import logging
from odoo import api, models, fields, _

logger = logging.getLogger(__name__)


class Task(models.Model):
    _name = 'project.task'
    _inherit = 'project.task'

    asterisk_calls_count = fields.Integer(compute='_get_asterisk_calls_count',
                                          string=_('Calls'))
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')
    recorded_calls = fields.One2many(
        'asterisk_plus.recording', 'task')

    def _get_asterisk_calls_count(self):
        for rec in self:
            rec.asterisk_calls_count = self.env[
                'asterisk_plus.call'].search_count(
                    [('res_id', '=', rec.id), ('model', '=', 'project.task')])

    @api.model
    def create(self, vals):
        res = super(Task, self).create(vals)
        try:
            if self.env.context.get('call_id'):
                call = self.env['asterisk_plus.call'].browse(
                    self.env.context['call_id'])
                call.write({
                    'res_id': res.id,
                    'model': 'project.task'})
        except Exception as e:
            logger.exception(e)
        if res:
            self.pool.clear_caches()
        return res
