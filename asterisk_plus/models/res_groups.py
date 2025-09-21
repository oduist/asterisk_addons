import json
import logging
from odoo import models, fields, api, tools, release, release, _
from odoo.exceptions import ValidationError, UserError
from .settings import debug

logger = logging.getLogger(__name__)


class ResUser(models.Model):
    _inherit = 'res.groups'

    @api.constrains('users')
    def _manage_pbx_users(self):
        if self.env.context.get('install_mode'):
            return
        server = self.env.ref('asterisk_plus.default_server')
        if not server.auto_create_pbx_users:
            debug(self, 'Auto create PBX users not enabled.')
            return
        pbx_users = self.env['asterisk_plus.user'].search([]).mapped('user')
        pbx_group = self.env.ref('asterisk_plus.group_asterisk_user')
        for rec in self:
            if rec.id != pbx_group.id:
                # Not a PBX user group.
                continue
            new_users = rec.users - pbx_users
            # Create new users
            self.env['asterisk_plus.user'].auto_create(new_users)
            remove_pbx_users = pbx_users - rec.users
            for user in remove_pbx_users:
                pbx_user = self.env['asterisk_plus.user'].search([('user', '=', user.id)])
                pbx_user.channels.unlink()
                pbx_user.unlink()
