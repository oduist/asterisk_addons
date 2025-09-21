from . import controllers
from . import models
from . import reports
from . import wizard

import logging
from odoo import api, SUPERUSER_ID
logger = logging.getLogger(__name__)

def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        env['asterisk_plus.settings'].update_billing_data()
        logger.info('Asterisk Plus post init hook done.')
    except Exception as e:
        logger.warning('Cannot update billing data after module upgrade, do it manually!')
