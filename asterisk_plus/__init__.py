from . import controllers
from . import models
from . import reports
from . import wizard

import logging
from odoo import fields, api
from odoo.api import SUPERUSER_ID

_logger = logging.getLogger(__name__)
def post_init_hook(*args):
    try:
        if len(args) == 1:
            env = args[0]
        else:
            cr, registry = args
            env = api.Environment(cr, SUPERUSER_ID, {})
        module = env['ir.module.module'].search([('name', '=', 'asterisk_plus')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))
