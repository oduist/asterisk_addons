from odoo.tools.sql import rename_column
from odoo import api
from odoo.api import SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    print('Removing unused code...')
    recs = env['ir.model.data'].search([('name','like','asterisk_plus_create_subscription_wizard')]).unlink()
    if recs:
        print('Removed asterisk_plus_create_subscription_wizard.')
