import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


logger = logging.getLogger(__name__)


class CallSource(models.Model):
    _inherit = 'utm.source'

    phone = fields.Char()

    _sql_constraints = [('phone_uniq', 'UNIQUE(phone)', 'This phone number is already used!')]

