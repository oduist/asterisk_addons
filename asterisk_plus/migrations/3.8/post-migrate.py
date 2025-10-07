from odoo.tools.sql import rename_column
from odoo import api
from odoo.api import SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    print('Upgrading Asterisk Plus users DID number...')
    users = env['asterisk_plus.user'].search([])
    for user in users:
        user.write({
            'did_number': user.phone,
            'callerid_number': user.exten,
        })
    print('PBX Users migrated.')

