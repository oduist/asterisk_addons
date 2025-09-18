# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class APITalkButton(http.Controller):
    @http.route('/get_talk_param/', type='json', auth='public', sitemap=False)
    def web_map(self):
        return {
            'talkbtn_sip_user': request.env['ir.config_parameter'].sudo().get_param('asterisk_plus_website.talkbtn_sip_user'),
            'talkbtn_sip_secret': request.env['ir.config_parameter'].sudo().get_param('asterisk_plus_website.talkbtn_sip_secret'),
            'talkbtn_exten': request.env['ir.config_parameter'].sudo().get_param('asterisk_plus_website.talkbtn_exten'),
            'talkbtn_sip_proxy': request.env['ir.config_parameter'].sudo().get_param('asterisk_plus_website.talkbtn_sip_proxy'),
            'talkbtn_websocket': request.env['ir.config_parameter'].sudo().get_param('asterisk_plus_website.talkbtn_websocket'),
            'talkbtn_sip_protocol': request.env['ir.config_parameter'].sudo().get_param('asterisk_plus_website.talkbtn_sip_protocol')
        }
