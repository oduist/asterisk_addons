# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2020
import logging
import re
import phonenumbers
from phonenumbers import phonenumberutil
from odoo import models, fields, api, tools, release, _
from .settings import debug, MAX_EXTEN_LEN

logger = logging.getLogger(__name__)

# Skip searching for numbers less then MAX_EXTEN_LEN


def strip_number(number):
    """Strip number formating"""
    if not isinstance(number, str):
        return number
    pattern = r'[\s\(\)\-\+]'
    return re.sub(pattern, '', number).lstrip('0')

def format_number(self, number, country=None, format_type='e164'):
    """Return number in requested format_type
    """
    res = False
    try:
        phone_nbr = phonenumbers.parse(number, country)
        if not phonenumbers.is_possible_number(phone_nbr):
            debug(self, '{} country {} parse impossible'.format(
                number, country
            ))
        # We have a parsed number, let check what format to return.
        elif format_type == 'e164':
            res = phonenumbers.format_number(
                phone_nbr, phonenumbers.PhoneNumberFormat.E164)
        else:
            logger.error('WRONG FORMATTING PASSED: %s', format_type)
    except phonenumberutil.NumberParseException:
        debug(self, '{} {} {} got NumberParseException'.format(
            number, country, format_type
        ))
    except Exception:
        logger.exception('FORMAT NUMBER ERROR: ')
    finally:
        debug(self, '{} county {} format {}: {}'.format(
            number, country, format_type, res))
        return res or number


class Partner(models.Model):
    _inherit = ['res.partner']

    phone_normalized = fields.Char(compute='_get_phone_normalized',
                                   index=True, store=True,
                                   string='E.164 phone')
    mobile_normalized = fields.Char(compute='_get_phone_normalized',
                                    index=True, store=True,
                                    string='E.164 mobile')
    phone_extension = fields.Char(help=_(
        'Prefix with # to add 1 second pause before entering. '
        'Every # adds 1 second pause. Example: ###1001'))
    call_count = fields.Integer(compute='_get_call_count', string='Calls')
    recorded_calls = fields.One2many('asterisk_plus.recording', 'partner')

    @api.model
    def create(self, vals):
        try:
            if self.env.context.get('call_id'):
                call = self.env['asterisk_plus.call'].browse(
                    self.env.context['call_id'])
                if call.direction == 'in':
                    vals['phone'] = call.calling_number
                else:
                    vals['phone'] = call.called_number
        except Exception as e:
            logger.exception(e)
        res = super().create(vals)
        if res and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    def write(self, values):
        res = super().write(values)
        if res and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    def unlink(self):
        res = super().unlink()
        if res and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    @api.model
    def originate_call(self, number, model=None, res_id=None, exten=None):
        """Originate Call to partner.

        Args:
            number (str): Number to dial.
            exten (str): Optional extension number to enter in DTMF mode after answer.
        """
        partner = self.browse(res_id)
        number = partner.phone_normalized
        extension = partner.phone_extension or ''
        # Minimum 1 second delay.
        dtmf_delay = extension.count('#') or 1
        # Now strip # and have only extension.
        dtmf_digits = extension.strip('#')
        self.env.user.asterisk_users[0].server.originate_call(
            number, model='model', res_id=res_id,
            dtmf_variables=['__dtmf_digits: {}'.format(dtmf_digits),
                            '__dtmf_delay: {}'.format(dtmf_delay)])

    @api.depends('phone', 'mobile', 'country_id')
    def _get_phone_normalized(self):
        for rec in self:
            rec.update({
                'phone_normalized': rec._normalize_phone(rec.phone) if rec.phone else False,
                'mobile_normalized': rec._normalize_phone(rec.mobile) if rec.mobile else False
            })

    def _normalize_phone(self, number):
        """Keep normalized phone numbers in normalized fields.
        """
        self.ensure_one()
        if self.env['asterisk_plus.settings'].sudo().get_param('disable_phone_format'):
            return number
        country = self._get_country()
        try:
            phone_nbr = phonenumbers.parse(number, country)
            if phonenumbers.is_possible_number(phone_nbr) or \
                    phonenumbers.is_valid_number(phone_nbr):
                number = phonenumbers.format_number(
                    phone_nbr, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.phonenumberutil.NumberParseException:
            # Force the number to be E.164 format.
            number = '+{}'.format(strip_number(number))
        except Exception as e:
            logger.warning('Normalize phone error: %s', e)
        # Strip the number if parse error.
        return number

    def search_by_number(self, number):
        """Search partner by number.
        Args:
            number (str): number to be searched on.
        If several partners are found by the same number:
        a) If partners belong to same company, return company record.
        b) If partners belong to different companies return False.
        """
        search_operation = self.env['asterisk_plus.settings'].sudo(
            ).get_param('number_search_operation')
        found = self.search([
            '|',
            ('phone_normalized', search_operation, number),
            ('mobile_normalized', search_operation, number)])
        debug(self, '{} belongs to partners: {}'.format(
            number, found.mapped('id')
        ))
        parents = found.mapped('parent_id')
        # 1-st case: just one partner, perfect!
        if len(found) == 1:
            return found
        # 2-nd case: Many partners, no parent company / many companies
        elif len(parents) == 0 and len(found) > 1:
            logger.warning('MANY PARTNERS FOR NUMBER %s', number)
            return found[0]
        # 3-rd case: many partners, many companies
        elif len(parents) > 1 and len(found) > 1:
            logger.warning(
                'MANY PARTNERS DIFFERENT COMPANIES FOR NUMBER %s', number)
            return
        # 4-rd case: 1 partner from one company
        elif len(parents) == 1 and len(found) == 2 and len(
                found.filtered(
                    lambda r: r.parent_id.id in [k.id for k in parents])) == 1:
            debug(self, 'one partner from one parent found')
            return found.filtered(
                lambda r: r.parent_id in [k for k in parents])[0]
        # 5-rd case: many partners same parent company
        elif len(parents) == 1 and len(found) > 1 and len(found.filtered(
                lambda r: r.parent_id in [k for k in parents])) > 1:
            debug(self, 'MANY PARTNERS SAME PARENT COMPANY {}'.format(number))
            return parents[0]

    def _get_country(self):
        partner = self
        if partner and partner.country_id:
            # Return partner country code
            return partner.country_id.code
        elif partner and partner.parent_id and partner.parent_id.country_id:
            # Return partner's parent country code
            return partner.parent_id.country_id.code
        elif partner and partner.company_id and partner.company_id.country_id:
            # Return partner's company country code
            return partner.company_id.country_id.code
        elif self.env.user and self.env.user.company_id.country_id:
            # Return Odoo's main company country
            return self.env.user.company_id.country_id.code

    @api.model
    @tools.ormcache('number', 'country')
    def get_partner_by_number(self, number, country=None):
        number = strip_number(number)
        if (not number or 'unknown' in number or
                number == 's'):
            debug(self, '{} skip search'.format(number))
            return {'name': _('Unknown'), 'id': False}
        partner = None
        # Search by stripped number prefixed with '+'
        number_plus = '+' + number
        partner = self.search_by_number(number_plus)
        if partner:
            return {'id': partner.id, 'name': partner.display_name }
        # Search by stripped number
        partner = self.search_by_number(number)
        if partner:
            return {'id': partner.id, 'name': partner.display_name }
        # Search by number in e164 format
        e164_number = format_number(self,
            number, country=country, format_type='e164')
        if e164_number and e164_number not in [number, number_plus]:
            partner = self.search_by_number(e164_number)
        if partner:
            return {'id': partner.id, 'name': partner.display_name }
        else:
            return {'name': _('Unknown'), 'id': False}

    def _get_call_count(self):
        for rec in self:
            if rec.is_company:
                rec.call_count = self.env[
                    'asterisk_plus.call'].sudo().search_count(
                    ['|', ('partner', '=', rec.id),
                          ('partner.parent_id', '=', rec.id)])
            else:
                rec.call_count = self.env[
                    'asterisk_plus.call'].sudo().search_count(
                    [('partner', '=', rec.id)])

    def _phone_format(self, number=None, country=None, company=None, force_format='E164', **kwargs):
        disable = self.env['asterisk_plus.settings'].sudo().get_param('disable_phone_format')
        if disable:
            return strip_number(number)
        version_info = release.version_info
        # For Odoo versions before 16
        if version_info[0] < 16:
            return super(Partner, self)._phone_format(number, country=country, company=company)
        # For Odoo version 16
        elif version_info[0] == 16:
            return super(Partner, self)._phone_format(number, country=country, company=company, force_format=force_format)
        # For Odoo version 17 and later
        else:
            # Ensure 'fname' and 'raise_exception' are extracted from kwargs or set to defaults
            fname = kwargs.get('fname', False)
            raise_exception = kwargs.get('raise_exception', False)
            return super(Partner, self)._phone_format(fname=fname, number=number, country=country, force_format=force_format, raise_exception=raise_exception)
