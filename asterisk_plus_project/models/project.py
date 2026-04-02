import logging
from odoo import api, models, fields, tools, release
from odoo.addons.asterisk_plus.models.license import ODUIST_MODULES

ODUIST_MODULES.append('asterisk_plus_project')

logger = logging.getLogger(__name__)


class Project(models.Model):
    _name = 'project.project'
    _inherit = 'project.project'

    asterisk_calls_count = fields.Integer(compute='_get_asterisk_calls_count', string='Calls')
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')
    recorded_calls = fields.One2many('asterisk_plus.recording', 'project')

    def _get_asterisk_calls_count(self):
        for rec in self:
            rec.asterisk_calls_count = self.env[
                'asterisk_plus.call'].search_count(
                    [('res_id', '=', rec.id), ('model', '=', 'project.project')])

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            try:
                if self.env.context.get('call_id'):
                    call = self.env['asterisk_plus.call'].browse(self.env.context['call_id'])
                    if call.partner:
                        val['partner_id'] = call.partner.id
            except Exception as e:
                logger.exception(e)
        res = super(Project, self).create(vals_list)
        if res:
            if release.version_info[0] >= 17:
                self.invalidate_model(flush=True)
            else:
                self.clear_caches()
        return res
