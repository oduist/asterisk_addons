# -*- coding: utf-8 -*

import logging
from phonenumbers import phonenumberutil
import phonenumbers
from odoo import api, models, tools, release, fields, release
from odoo.exceptions import ValidationError, UserError
from odoo.addons.asterisk_plus.models.settings import debug, MAX_EXTEN_LEN
from odoo.addons.asterisk_plus.models.res_partner import strip_number
from odoo.addons.asterisk_plus.models.res_partner import format_number

logger = logging.getLogger(__name__)


class Lead(models.Model):
    _inherit = 'crm.lead'

    if release.version_info[0] >= 19:
        mobile = fields.Char()
    asterisk_calls_count = fields.Integer(
        compute='_get_asterisk_calls_count', string='Calls', compute_sudo=True)
    phone_normalized = fields.Char(compute='_get_phone_normalized',
                                   index=True, store=True)
    mobile_normalized = fields.Char(compute='_get_phone_normalized',
                                    index=True, store=True)

    def write(self, values):
        res = super(Lead, self).write(values)
        if res:
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    def unlink(self):
        res = super(Lead, self).unlink()
        if res:
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        try:
            if self.env.context.get('call_id'):
                call = self.env['asterisk_plus.call'].browse(
                    self.env.context['call_id'])
                for vals in vals_list:
                    # Get call source
                    source = self.env['utm.source'].sudo().search(
                        [('phone', '=', call.called_number)], limit=1)
                    if source:
                        vals['source_id'] = source.id
                    if call.direction == 'in':
                        vals['phone'] = call.calling_number
                    else:
                        vals['phone'] = call.called_number
                    if call.partner:
                        vals['partner_id'] = call.partner.id
                    # A multicompany check
                    if hasattr(call, 'company_id'):
                        vals['company_id'] = call.company_id.id
        except Exception as e:
            logger.exception(e)
        res = super(Lead, self).create(vals_list)
        if res:
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    @api.depends('phone', 'mobile', 'country_id', 'partner_id', 'partner_id.phone', 'partner_id.mobile')
    def _get_phone_normalized(self):
        for rec in self:
            if release.version_info[0] >= 14:
                # Odoo > 14.0
                if rec.phone:
                    rec.phone_normalized = rec.normalize_phone(rec.phone)
                if rec.mobile:
                    rec.mobile_normalized = rec.normalize_phone(rec.mobile)
            else:
                # Old Odoo versions
                if rec.partner_id:
                    # We have partner set, take phones from him.
                    if rec.partner_address_phone:
                        rec.phone_normalized = rec.normalize_phone(
                            rec.partner_address_phone)
                    if rec.mobile:
                        rec.mobile_normalized = rec.normalize_phone(rec.mobile)
                else:
                    # No partner set takes phones from lead.
                    if rec.phone:
                        rec.phone_normalized = rec.normalize_phone(rec.phone)
                    if rec.mobile:
                        rec.mobile_normalized = rec.normalize_phone(rec.mobile)

    def _get_country(self):
        if self and self.country_id:
            return self.country_id.code
        elif self and self.partner_id and self.partner_id.country_id:
            return self.partner_id._get_country()
        else:
            if self.env.user and self.env.user.company_id.country_id:
                # Return Odoo's main company country
                return self.env.user.company_id.country_id.code

    def normalize_phone(self, number):
        self.ensure_one()
        number = strip_number(number)
        country = self._get_country()
        try:
            phone_nbr = phonenumbers.parse(number, country)
            if phonenumbers.is_possible_number(phone_nbr):
                number = phonenumbers.format_number(
                    phone_nbr, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.phonenumberutil.NumberParseException:
            pass
        except Exception as e:
            logger.warning('Normalize phone error: %s', e)
        # Strip the number if no phone validation installed or parse error.
        return number

    def _get_asterisk_calls_count(self):
        for rec in self:
            rec.asterisk_calls_count = self.env[
                'asterisk_plus.call'].search_count(
                    [('res_id', '=', rec.id), ('model', '=', 'crm.lead')])

    def _search_lead_by_number(self, number):
        # Odoo <= 12 does not have 'is_won' field
        try:
            open_stages_ids = [k.id for k in self.env['crm.stage'].search(
                [('is_won', '=', False)])]
        except:
            open_stages_ids = [k.id for k in self.env['crm.stage'].search([])]
        domain = [
            ('active', '=', True),
            '|',
            ('stage_id', 'in', open_stages_ids),
            ('stage_id', '=', False),
            '|',
            ('phone_normalized', '=', number),
            ('mobile_normalized', '=', number)]
        found = self.env['crm.lead'].sudo().search(domain, order='id desc')
        if len(found) > 1:
            logger.warning('[ASTCALLS] MULTIPLE LEADS FOUND BY NUMBER %s', number)
        debug(self, 'Number {} belongs to leads: {}'.format(
            number, found.mapped('id')
        ))
        return found[:1]

    @tools.ormcache('number', 'country')
    def get_lead_by_number(self, number, country=None):
        number = strip_number(number)
        if (not number or 'unknown' in number or
            number == 's' or len(number) < MAX_EXTEN_LEN
        ):
            debug(self, '{} skip search'.format(number))
            return
        lead = None
        # Search by stripped number prefixed with '+'
        number_plus = '+' + number
        lead = self._search_lead_by_number(number_plus)
        if lead:
            return lead
        # Search by stripped number
        lead = self._search_lead_by_number(number)
        if lead:
            return lead
        # Search by number in e164 format
        e164_number = format_number(
            self, number, country=country, format_type='e164')
        if e164_number not in [number, number_plus]:
            lead = self._search_lead_by_number(e164_number)
        if lead:
            return lead
