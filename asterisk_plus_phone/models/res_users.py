# -*- coding: utf-8 -*-
from odoo import models, api


class User(models.Model):
    _inherit = "res.users"

    @api.model
    def get_sip_user_config(self, user_id):
        domain = [
            ("user", "=", user_id),
            ("sip_transport", "=", "webrtc-user"),
            ("sip_password", "!=", False),
        ]
        fields_list = ["sip_user", "sip_password", "sip_auth_user"]
        # Return only WebRTC transport channel.
        user_config = self.env["asterisk_plus.user_channel"].search_read(
            domain=domain, fields=fields_list, limit=1
        )
        user_config = user_config[0] if user_config else False

        fields_list = [
            "phone_ring_volume",
            "call_popup_is_enabled",
            "call_popup_is_sticky",
            "mask_call_number",
        ]
        phone_config = self.env["asterisk_plus.user"].search_read(
            domain=[("user", "=", user_id)], fields=fields_list, limit=1
        )
        phone_config = phone_config[0] if phone_config else False

        return {"user_config": user_config, "phone_config": phone_config}
