import logging
from odoo import models, fields, api, release
from odoo.exceptions import ValidationError


logger = logging.getLogger(__name__)


class CallSource(models.Model):
    _inherit = 'utm.source'

    phone = fields.Char()

    if release.version_info[0] >= 19:
        _phone_uniq = models.Constraint('UNIQUE(phone)', 'This phone number is already used!')
    else:
        _sql_constraints = [
            ('phone_uniq', 'UNIQUE(phone)', 'This phone number is already used!')
        ]

