# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2020
from odoo import fields, models


class CallsCrmSettings(models.Model):
    _inherit = 'asterisk_plus.settings'

    # Incoming calls
    auto_create_leads_for_in_calls = fields.Boolean(
        string='Auto Create Leads')
    auto_create_leads_for_in_answered_calls = fields.Boolean(
        help='Auto create leads for incoming answered calls.',
        string='For Answered Calls', default=True)
    auto_create_leads_for_in_missed_calls = fields.Boolean(
        help='Auto create leads for incoming missed calls.',
        string='For Not Answered Calls', default=True)
    auto_create_leads_for_in_unknown_callers = fields.Boolean(
        help='Auto create leads for callers that do not exist in Contacts.',
        string='For Unknown Callers', default=False)
    # Outgoing calls
    auto_create_leads_for_out_calls = fields.Boolean(
        string='Auto Create Leads')
    auto_create_leads_for_out_answered_calls = fields.Boolean(
        help='Auto create leads for outgoing answered calls.',
        string='For Answered Calls', default=True)
    auto_create_leads_for_out_missed_calls = fields.Boolean(
        help='Auto create leads for outgoing not connected calls.',
        string='For Not Answered Calls', default=True)
    # Leads type and default responsible.
    auto_create_leads_sales_person = fields.Many2one(
        'res.users',
        domain=[('share', '=', False)],
        string='Default Salesperson')
    auto_create_leads_type = fields.Selection(string='Leads type',
        default='lead', required=True,
        selection=[('lead', 'Lead'), ('opportunity', 'Opportunity')])
