# -*- coding: utf-8 -*-
from odoo import api, fields, models


class Settings(models.Model):
    _inherit = "asterisk_plus.settings"

    phone_enabled = fields.Boolean(string="Enabled", default=False)
    sentry_enabled = fields.Boolean(string="Sentry Enabled", default=False)
    phone_sip_protocol = fields.Char(string="SIP Protocol", default="wss")
    phone_realm = fields.Char(string="Realm", default="asterisk")
    phone_sip_proxy = fields.Char(string="SIP Proxy")
    phone_websocket = fields.Char(string="WebSocket")
    phone_stun_server = fields.Char(
        string="STUN Server", default="stun.l.google.com:19302"
    )
    phone_sip_auth_user_enabled = fields.Boolean(string="SIP Auth User Enabled")
    attended_transfer_sequence = fields.Char(default="*7", required=True)
    disconnect_call_sequence = fields.Char(default="**", required=True)
    transfer_contact_search = fields.Selection(
        [("extensions", "Extensions"), ("partners", "Partners"), ("all", "All")],
        default="all",
    )
    trace_sip = fields.Boolean(default=False)

    @api.model
    def get_settings(self):
        settings = self.search([], limit=1)
        return {
            "user_agent": {
                "phone_sip_protocol": settings.phone_sip_protocol,
                "phone_sip_proxy": settings.phone_sip_proxy,
                "phone_websocket": settings.phone_websocket,
                "phone_stun_server": settings.phone_stun_server,
                "phone_realm": settings.phone_realm,
            },
            "attended_transfer_sequence": settings.attended_transfer_sequence,
            "disconnect_call_sequence": settings.disconnect_call_sequence,
            "transfer_contact_search": settings.transfer_contact_search,
            "trace_sip": settings.trace_sip,
            "phone_sip_auth_user_enabled": settings.phone_sip_auth_user_enabled,
        }
