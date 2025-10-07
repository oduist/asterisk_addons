from odoo.tools.sql import rename_column
from odoo import api
from odoo.api import SUPERUSER_ID


def migrate(cr, version):
    print('Asterisk Plus 4.0 migration done.')
