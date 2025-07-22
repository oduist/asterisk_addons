# -*- coding: utf-8 -*-
from odoo import models, fields, api, release
from odoo.exceptions import ValidationError
from odoo.addons.asterisk_plus.models.user import USER_PERMITTED_FIELDS

USER_PERMITTED_FIELDS.append("phone_ring_volume")


class UserChannel(models.Model):
    _inherit = "asterisk_plus.user_channel"

    sip_auth_user = fields.Char(string="SIP Auth User")


class User(models.Model):
    _inherit = "asterisk_plus.user"

    phone_ring_volume = fields.Integer(
        string="Phone Ring Volume, %", required=True, default=100
    )
    mask_call_number = fields.Boolean(default=False)
    sip_auth_user_enabled = fields.Boolean(compute="_get_sip_auth_user_enabled")

    def _get_sip_auth_user_enabled(self):
        sip_auth_user_enabled = (
            self.env["asterisk_plus.settings"]
            .sudo()
            .get_param("phone_sip_auth_user_enabled")
        )
        for rec in self:
            rec.sip_auth_user_enabled = sip_auth_user_enabled

    @api.model
    def get_param(self, param, default=False):
        self.check_access_rule('read') if release.version_info[0] < 18 else self.check_access('read')
        data = self.search([])
        if not data:
            data = self.sudo().with_context(no_constrains=True).create({})
        else:
            data = data[0]
        return getattr(data, param, default)

    @api.constrains("phone_ring_volume")
    def _check_phone_ring_volume(self):
        for rec in self:
            if rec.phone_ring_volume < 0 or rec.phone_ring_volume > 100:
                raise ValidationError("Volume must be in a range from 0 to 100%!")

    @api.model
    def search_pbx_users(self, search_query):
        if not self.env.user.has_group("asterisk_plus.group_asterisk_user"):
            raise ValidationError("Only PBX users can search other PBX users!")
        domain = [
            "|",
            ["exten", "=ilike", f"%{search_query}%"],
            ["user", "=ilike", f"%{search_query}%"],
        ]
        search_fields = ["id", "name", "exten", "user"]
        users = self.sudo().search_read(
            domain, search_fields, limit=10, order="exten asc"
        )
        return users

    @api.model
    def get_user_by_number(self, search_query):
        if not self.env.user.has_group("asterisk_plus.group_asterisk_user"):
            raise ValidationError("Only PBX users can search other PBX users!")
        domain = [["exten", "=", search_query]]
        search_fields = ["id", "name", "exten", "user"]
        user = self.sudo().search_read(
            domain, search_fields, limit=1, order="exten asc"
        )
        return user[0] if user else False
