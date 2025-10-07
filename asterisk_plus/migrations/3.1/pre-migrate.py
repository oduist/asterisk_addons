import logging
from odoo import api
from odoo.api import SUPERUSER_ID
from odoo.tools.sql import rename_column

logger = logging.getLogger(__name__)

def check_for_column(env, table_name, column_name):
    query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name=%s AND column_name=%s;
    """
    env.cr.execute(query, (table_name, column_name))
    result = env.cr.fetchone()
    return bool(result)    

def migrate(cr, version):
    print('Migrating answered user...')
    env = api.Environment(cr, SUPERUSER_ID, {})
    if check_for_column(env, 'asterisk_plus_call', 'called_user'):
        rename_column(cr, 'asterisk_plus_call', 'called_user', 'answered_user')
    print('Answered user column migrated.')
