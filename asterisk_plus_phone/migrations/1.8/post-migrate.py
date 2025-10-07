from odoo.tools.sql import rename_column
from odoo import api
from odoo.api import SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    print('Migrating Asterisk Plus phone Via transport...')
    env['asterisk_plus.settings'].set_param('phone_sip_protocol', 'wss')
