import json
import logging
from odoo import models, fields, api, tools, release, release
from odoo.exceptions import ValidationError, UserError
from .settings import debug

logger = logging.getLogger(__name__)


class ResUser(models.Model):
    _inherit = 'res.users'

    asterisk_users = fields.One2many(
        'asterisk_plus.user', inverse_name='user')
    # Server of Agent account, One2one simulation.
    asterisk_server = fields.Many2one('asterisk_plus.server', compute='_get_asterisk_server')

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        for user in users:
            if not user.has_group('asterisk_plus.group_asterisk_user'):
                # We create PBX users only for users who have PBX group.
                return user
            debug(self, "Created user {}".format(user.login))
            # create SIP account if enabled and not when installing.
            if not self.env.context.get('install_mode'):
                self.env['asterisk_plus.user'].auto_create(user)
        return users

    @api.constrains('group_ids')
    def _manage_pbx_users(self):
        if self.env.context.get('install_mode'):
            return
        server = self.env.ref('asterisk_plus.default_server').sudo()
        if not server.auto_create_pbx_users:
            debug(self, 'Auto create PBX users not enabled.')
            return
        if not (self.env.user.has_group('base.group_erp_manager') or
                self.env.user.has_group('base.group_system')):
            logger.warning('Skippung PBX users auto create.')
            return
        add_pbx_users = []
        remove_pbx_users = []
        for rec in self:
            if rec.has_group('asterisk_plus.group_asterisk_user'):
                add_pbx_users.append(rec)
            else:
                remove_pbx_users.append(rec)
        if add_pbx_users:
            self.env['asterisk_plus.user'].sudo().auto_create(add_pbx_users)
        if remove_pbx_users:
            for user in remove_pbx_users:
                pbx_user = self.env['asterisk_plus.user'].sudo().search([('user', '=', user.id)])
                pbx_user.channels.unlink()
                pbx_user.unlink()

    def _get_asterisk_server(self):
        for rec in self:
            # There is an unique constraint to limit 1 user per server.
            rec.asterisk_server = self.env['asterisk_plus.server'].search(
                [('user', '=', rec.id)], limit=1)
