from odoo import api, models, fields


class Recording(models.Model):
    _name = 'asterisk_plus.recording'
    _inherit = 'asterisk_plus.recording'

    task = fields.Many2one('project.task', ondelete='set null', readonly=True)
    project = fields.Many2one('project.project', ondelete='set null', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super(Recording, self.with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True)).create(vals_list)
        for rec in recs:
            if rec.call.model == 'project.project' and rec.call.ref:
                rec.project = rec.call.ref
            elif rec.call.model == 'project.task' and rec.call.ref:
                rec.task = rec.call.ref
        return recs
