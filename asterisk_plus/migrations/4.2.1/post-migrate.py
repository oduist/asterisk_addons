from odoo import api
from odoo.api import SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Reset admin name to migrate registration fields.
    env['asterisk_plus.settings'].set_param('admin_name', '')
    print('Asterisk Plus app migration is done.')
