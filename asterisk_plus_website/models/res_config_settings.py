# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    talkbtn_sip_user = fields.Char(
        string='SIP User',
        config_parameter='asterisk_plus_website.talkbtn_sip_user')
    talkbtn_sip_secret = fields.Char(
        string='SIP Secret',
        config_parameter='asterisk_plus_website.talkbtn_sip_secret')
    talkbtn_exten = fields.Char(
        string='Exten',
        config_parameter='asterisk_plus_website.talkbtn_exten')
    talkbtn_sip_proxy = fields.Char(
        string='Sip Proxy',
        config_parameter='asterisk_plus_website.talkbtn_sip_proxy')
    talkbtn_websocket = fields.Char(
        string='Websocket',
        config_parameter='asterisk_plus_website.talkbtn_websocket')
    talkbtn_sip_protocol = fields.Char(
        string='Sip Protocol',
        default='udp',
        config_parameter='asterisk_plus_website.talkbtn_sip_protocol')
    talkbtn_stun_server = fields.Char(
        string='Stun Server',
        default='stun.l.google.com:19302',
        config_parameter='asterisk_plus_website.talkbtn_stun_server')
