# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2021
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.addons.asterisk_plus.models.settings import debug


logger = logging.getLogger(__name__)


class CrmCall(models.Model):
    _inherit = 'asterisk_plus.call'

    ref = fields.Reference(selection_add=[('crm.lead', 'Leads')])
    source = fields.Many2one('utm.source')

    def update_reference(self, **kwargs):
        country = kwargs['country'] if 'country' in kwargs else None
        res = super(CrmCall, self).update_reference(**kwargs)
        # Update call source
        self.source = self.env['utm.source'].sudo().search(
            [('phone', '=', self.called_number)], limit=1)
        # Update reference if not set.
        if not res:
            lead = None
            # No reference was set, so we have a change to set it to a lead
            if self.direction == 'in':                
                lead = self.env['crm.lead'].get_lead_by_number(
                    self.calling_number, country=country)
            else:
                lead = self.env['crm.lead'].get_lead_by_number(
                    self.called_number, country=country)
            if lead:
                debug(self, 'Call {} assign {}'.format(self.id, lead))
                self.ref = lead
                return True
            else:
                # No lead is found but probably we should create one.
                return self.sudo()._auto_create_lead(country=country)
        else:
            debug(self, 'CRM: Not updating reference as already set.')

    def _auto_create_lead(self, country=None):
        self.ensure_one()
        # Do not consider reference to a partner as a condition to skip
        if self.ref and not self.ref._name == 'res.partner':
            debug(self, '{} reference already set: {}'.format(self.id, self.ref))
            return False
        # Skip if direction is unkown
        if not self.direction:
            debug(self, 'Call direction undefined for : {}'.format(self.id))
            return False
        auto_create_leads_for_in_calls = self.env[
            'asterisk_plus.settings'].get_param(
            'auto_create_leads_for_in_calls')
        auto_create_leads_for_out_calls = self.env[
            'asterisk_plus.settings'].get_param(
            'auto_create_leads_for_out_calls')
        auto_create_leads_for_in_answered_calls = self.env[
            'asterisk_plus.settings'].get_param(
            'auto_create_leads_for_in_answered_calls')
        auto_create_leads_for_in_missed_calls = self.env[
            'asterisk_plus.settings'].get_param(
            'auto_create_leads_for_in_missed_calls')
        auto_create_leads_for_in_unknown_callers = self.env[
            'asterisk_plus.settings'].get_param(
            'auto_create_leads_for_in_unknown_callers')
        auto_create_leads_for_out_calls = self.env[
            'asterisk_plus.settings'].get_param(
            'auto_create_leads_for_out_calls')
        auto_create_leads_for_out_answered_calls = self.env[
            'asterisk_plus.settings'].get_param(
            'auto_create_leads_for_out_answered_calls')
        auto_create_leads_for_out_missed_calls = self.env[
            'asterisk_plus.settings'].get_param(
            'auto_create_leads_for_out_missed_calls')
        default_sales_person = self.env[
            'asterisk_plus.settings'].get_param(
            'auto_create_leads_sales_person')
        lead_type = self.env[
            'asterisk_plus.settings'].get_param(
            'auto_create_leads_type')
        # Get call source
        source = self.env['utm.source'].sudo().search(
            [('phone', '=', self.called_number)], limit=1)
        if self.direction == 'in':
            if not auto_create_leads_for_in_calls:
                debug(self, 'Autocreate not enabled for incomig calls')
                return False
            # Incoming answered call
            elif self.status == 'answered' \
                    and auto_create_leads_for_in_answered_calls:
                debug(self, 'Creating a lead for answered incoming call.')
            # Not answered 2nd leg and auto create for missed calls is set.
            elif self.status != 'answered' and \
                    auto_create_leads_for_in_missed_calls and \
                    not self.is_active:
                debug(self, 'Creating a lead for missed incoming call.')
            # Incoming Call from unknown caller.
            elif auto_create_leads_for_in_unknown_callers:
                debug(self, 'Creating a lead for unknown incoming call.')
            else:
                debug(self, 'No incoming rule matched for {}'.format(self.id))
                return False
            # Define a salesperson for the lead
            user_id = self.answered_user.id or self.called_users[:1].id
            if not user_id:
                user_id = self.env['asterisk_plus.user'].search(
                    [('exten', '=', self.called_number)],
                        limit=1).user.id
            if not user_id:
                user_id = default_sales_person.id
            # Data dict for created lead
            data = {
                'name': self.partner.name or self.calling_number,
                'type': lead_type,
                'user_id': user_id,
                'partner_id': self.partner.id,
                'source_id': source.id,
            }
            # set number only if partner is not set
            if not self.partner:
                data['phone'] = self.calling_number
        elif self.direction == 'out':
            if not auto_create_leads_for_out_calls:
                debug(self, 'Autocreate not enabled for outgoing calls')
                return False
            if self.called_users:
                debug(self, 'Autocreate skip "out" call to local users')
                return False
            # Answered call
            elif self.status == 'answered' \
                    and auto_create_leads_for_out_answered_calls:
                debug(self, 'Creating a lead for answered outgoing call.')
            # Not answered 2nd leg and auto create for missed calls is set.
            elif self.status != 'answered' and \
                    auto_create_leads_for_out_missed_calls and \
                    not self.is_active:
                debug(self, 'Creating a lead for missed outgoing call.')
            else:
                debug(self, 'No outgoing rule matched for {}'.format(self.id))
                return False
            # Data dict for created lead
            data = {
                'name': self.partner.name or self.called_number,
                'type': lead_type,
                'user_id': self.calling_user.id or default_sales_person.id,
                'partner_id': self.partner.id,
                'source_id': source.id,
            }
            # set number only if partner is not set
            if not self.partner:
                data['phone'] = self.called_number
        # Finally create a lead
        debug(self, 'Lead create data: {}'.format(data))
        lead = self.env['crm.lead'].create(data)
        debug(self, 'Set lead {} for call {}'.format(lead.id, self.id))
        self.ref = lead
        return True

    def lead_button(self):
        self.ensure_one()
        context = {}
        if not self.ref:
            # Create a new lead
            self.ref = self.env['crm.lead'].with_context(
                call_id=self.id).create({'name': self.calling_name or self.calling_number})
            context['form_view_initial_mode'] = 'edit'
        # Open call lead
        if self.ref._name == 'crm.lead':
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'crm.lead',
                'res_id': self.ref.id,
                'name': 'Call Lead',
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'current',
                'context': context,
            }
        else:
            raise ValidationError(_('Reference already defined!'))
